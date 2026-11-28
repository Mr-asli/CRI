import hmac
import os
import secrets
import time
import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from .config import validate_environment, env_bool
from .monitoring import Metrics, host_metrics
from .alerts import notify
from .quota import QuotaService
from pydantic import BaseModel, Field

from .self_improvement import ImprovementWorkflow
from .core import (
    Audit,
    Denied,
    Kill,
    Memory,
    Policy,
    Sandbox,
    SandboxUnavailable,
    Tokens,
    Workflow,
)
from .agents import AgentFactory
from .agents.developer import DeveloperUnavailable
from .agents.factory import AGENT_TYPES
from .tools import ToolGateway, ToolSpec
from .integrations.opa import OPAClient, OPAUnavailable, OPADenied, OPAPolicy
from .integrations.redis_store import RedisTTLStore
from .db import get_engine, session_factory, SQLRepository

DATA = os.getenv("CRI_DATA_DIR", "./data")
ADMIN_TOKEN = os.getenv("CRI_ADMIN_TOKEN", "")
APPROVAL_SECRET = os.getenv("CRI_APPROVAL_SECRET", "")
AUDIT = Audit(os.getenv("CRI_AUDIT_FILE", DATA + "/audit.jsonl"))
OPA_URL = os.getenv("CRI_OPA_URL") or os.getenv("OPA_URL")
OPA = OPAClient(OPA_URL) if OPA_URL else None
LOCAL_POLICY = Policy(AUDIT)
POLICY = OPAPolicy(LOCAL_POLICY, OPA) if OPA is not None else LOCAL_POLICY
KILL = Kill(os.getenv("CRI_KILL_FILE", DATA + "/KILL"))
MEMORY = Memory()
TOKENS = (
    Tokens(
        APPROVAL_SECRET,
        nonce_db=os.getenv("CRI_NONCE_DB", DATA + "/approval_nonces.sqlite3"),
    )
    if len(APPROVAL_SECRET.encode()) >= 32
    else None
)
FLOW = Workflow(AUDIT, POLICY, KILL, TOKENS, Sandbox()) if TOKENS else None
IMPROVEMENT_WORKFLOW = ImprovementWorkflow(AUDIT, TOKENS) if TOKENS else None
GATEWAY = ToolGateway(POLICY, AUDIT, KILL)
def _write_memory(payload):
    record = MEMORY.write("lesson", payload["text"])
    if DB_REPOSITORY is not None:
        DB_REPOSITORY.save_memory(record["kind"], record["text"])
    if REDIS_STORE is not None:
        REDIS_STORE.delete("memory:list")
        REDIS_STORE.put("memory:last", record, 3600)
    return record

GATEWAY.register(
    ToolSpec("memory.write", "memory_write", frozenset({"memory"}), _write_memory)
)
AGENT_FACTORY = AgentFactory(POLICY, GATEWAY)
DB_REPOSITORY = None
REDIS_STORE = None
WS_TICKETS = {}
METRICS = Metrics()
QUOTA = None


@asynccontextmanager
async def lifespan(app):
    global DB_REPOSITORY, REDIS_STORE, QUOTA
    validate_environment({**os.environ, "CRI_ADMIN_TOKEN": ADMIN_TOKEN, "CRI_APPROVAL_SECRET": APPROVAL_SECRET})
    if TOKENS is None:
        raise RuntimeError("CRI_APPROVAL_SECRET must be set to at least 32 bytes")

    engine = None
    redis_client = None
    database_url = os.getenv("CRI_DATABASE_URL") or os.getenv("DATABASE_URL")
    if database_url:
        engine = get_engine(database_url)
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
            if connection.dialect.name == "postgresql":
                required = connection.exec_driver_sql("""
                    SELECT
                      to_regclass('public.tasks') IS NOT NULL
                      AND to_regclass('public.audit_events') IS NOT NULL
                      AND to_regclass('public.memory_records') IS NOT NULL
                      AND to_regclass('public.improvement_records') IS NOT NULL
                      AND to_regclass('public.agent_states') IS NOT NULL
                      AND to_regclass('public.plans') IS NOT NULL
                      AND to_regclass('public.usage') IS NOT NULL
                      AND to_regclass('public.feature_flags') IS NOT NULL
                      AND to_regclass('public.quota_users') IS NOT NULL
                      AND EXISTS (SELECT 1 FROM information_schema.columns
                                  WHERE table_schema='public' AND table_name='audit_events' AND column_name='event_time')
                """).scalar()
                if not required:
                    raise RuntimeError("database schema is not current; run the CRI migration runner before startup")
        DB_REPOSITORY = SQLRepository(session_factory(engine))
        QUOTA = QuotaService(session_factory(engine), AUDIT, env_bool("QUOTA_ENABLED", True), env_bool("OWNER_BYPASS_QUOTA", True))
        AUDIT.db_writer = lambda row: DB_REPOSITORY.append_audit(
            row["event"], row["actor"], row["details"], row["prev"], row["hash"], row["time"]
        )
        # Replay local events idempotently after reconnecting to PostgreSQL.
        for pending_row in AUDIT.rows():
            if AUDIT.remote_sink is not None:
                AUDIT.remote_sink.append(pending_row)
            DB_REPOSITORY.append_audit(
                pending_row["event"], pending_row["actor"], pending_row["details"],
                pending_row["prev"], pending_row["hash"], pending_row["time"]
            )
        if FLOW is not None:
            FLOW.repository = DB_REPOSITORY
            FLOW.restore()
        if IMPROVEMENT_WORKFLOW is not None:
            IMPROVEMENT_WORKFLOW.repository = DB_REPOSITORY
            IMPROVEMENT_WORKFLOW.restore()

    redis_url = os.getenv("CRI_REDIS_URL") or os.getenv("REDIS_URL")
    if redis_url:
        try:
            import redis
            redis_client = redis.Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
            redis_client.ping()
            REDIS_STORE = RedisTTLStore(redis_client)
        except Exception as exc:
            raise RuntimeError("configured Redis is unavailable; refusing startup") from exc

    if OPA is not None:
        try:
            OPA.decide({"type": "human", "authenticated": True}, "api.access", {"startup": True})
        except Exception as exc:
            raise RuntimeError("configured OPA is unavailable or denies startup; refusing startup") from exc

    yield
    if redis_client is not None:
        redis_client.close()
    if engine is not None:
        engine.dispose()


app = FastAPI(title="CRI Control Plane", version="1.0.0", lifespan=lifespan)

class OperationalMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()
        quota_features = {("POST", "/api/tasks"): "task_create", ("POST", "/v1/tasks"): "task_create",
                          ("POST", "/api/agents/DeveloperAgent/run"): "agent_run",
                          ("POST", "/api/memory"): "memory_write", ("POST", "/v1/memory"): "memory_write"}
        feature = quota_features.get((request.method, request.url.path))
        if request.method == "POST" and request.url.path.startswith(("/api/agents/", "/v1/agents/")) and request.url.path.endswith("/run"):
            feature = "agent_run"
        principal = "human-admin"
        authenticated = hmac.compare_digest((request.headers.get("authorization", "").partition(" ")[2]), ADMIN_TOKEN) if ADMIN_TOKEN else False
        if feature and env_bool("QUOTA_ENABLED", True) and authenticated:
            if QUOTA is None:
                if os.getenv("CRI_DATABASE_URL") or os.getenv("DATABASE_URL"):
                    return JSONResponse(status_code=503, content={"detail":"quota database unavailable; request denied"})
            else:
                decision = QUOTA.check(principal, feature, is_owner=(principal == os.getenv("CRI_OWNER_USER_ID", "human-admin")))
                if not decision.allowed:
                    return JSONResponse(status_code=429, content={"detail":"quota exceeded", "reason":decision.reason, "used":decision.used, "limit":decision.limit})
        response = await call_next(request)
        elapsed = time.perf_counter()-started
        METRICS.observe(request.method, request.url.path, response.status_code, elapsed)
        if feature and authenticated and response.status_code < 400 and QUOTA is not None and not (env_bool("OWNER_BYPASS_QUOTA", True) and principal == os.getenv("CRI_OWNER_USER_ID", "human-admin")):
            QUOTA.record(principal, feature)
        return response

app.add_middleware(OperationalMiddleware)


class Goal(BaseModel):
    goal: str = Field(min_length=3, max_length=1000)


class Decision(BaseModel):
    proposal_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    decision: str
    reason: str = Field(min_length=3, max_length=500)
    token: str = Field(min_length=20, max_length=2048)


def require_admin(authorization: str | None = Header(default=None)):
    if not ADMIN_TOKEN or len(ADMIN_TOKEN.encode()) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="admin authentication is not configured",
        )
    scheme, _, supplied = (authorization or "").partition(" ")
    if (
        scheme.lower() != "bearer"
        or not supplied
        or not hmac.compare_digest(supplied, ADMIN_TOKEN)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if OPA is not None:
        try:
            OPA.decide({"type": "human", "authenticated": True}, "api.access", {"path": "control-plane"})
        except OPADenied as exc:
            raise HTTPException(status_code=403, detail="policy denied") from exc
        except OPAUnavailable as exc:
            raise HTTPException(status_code=503, detail="policy service unavailable; request denied") from exc
    return "human-admin"


@app.get("/api/status")
def status_view():
    sandbox = Sandbox()
    return {
        # This is only the application admission latch, not proof that host
        # processes are running or terminated.
        "status": "stopped" if KILL.active() else "enabled",
        "control_plane": "reachable",
        "audit": AUDIT.verify(),
        "sandbox": "configured_not_verified" if sandbox.docker_binary and "@sha256:" in sandbox.image else "unavailable",
        "execution_guarantee": "not_independently_supervised",
        "database": "connected" if DB_REPOSITORY is not None else "not_configured",
        "database_audit": DB_REPOSITORY.audit_status() if DB_REPOSITORY is not None else {"connected": False, "valid": False, "count": 0},
        "redis": "connected" if REDIS_STORE is not None else "not_configured",
        "opa": "configured" if OPA is not None else "not_configured",
        "remote_audit": "configured_receiver_not_verified" if AUDIT.remote_sink is not None else "not_configured",
        "host_watchdog": "deployment_required",
        "host": host_metrics(),
        "agent_heartbeats": REDIS_STORE.heartbeat_status() if REDIS_STORE is not None and hasattr(REDIS_STORE, "heartbeat_status") else {"available": False},
    }


@app.post("/api/ws-ticket")
def create_ws_ticket(_admin=Depends(require_admin)):
    now = time.time()
    for key, expiry in list(WS_TICKETS.items()):
        if expiry < now: WS_TICKETS.pop(key, None)
    ticket = secrets.token_urlsafe(32)
    WS_TICKETS[ticket] = now + 30
    return {"ticket": ticket, "expires_in": 30}


@app.websocket("/api/ws")
async def live_updates(websocket: WebSocket):
    ticket = websocket.query_params.get("ticket", "")
    expiry = WS_TICKETS.pop(ticket, 0) if ticket else 0
    if not expiry or expiry < time.time():
        await websocket.close(code=4401)
        return
    await websocket.accept()
    try:
        while True:
            state = {
                "type": "snapshot",
                "status": "stopped" if KILL.active() else "enabled",
                "audit": AUDIT.verify(),
                "database_audit": DB_REPOSITORY.audit_status() if DB_REPOSITORY is not None else None,
                "agents": [role for role in AGENT_TYPES],
                "timestamp": time.time(),
            }
            await websocket.send_json(state)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return


@app.get("/api/agents")
def agents():
    return [
        {
            "name": role,
            "role": role,
            "implemented": True,
            "status": "available_not_running",
            "capabilities": sorted(
                __import__("cri.core", fromlist=["ROLES"]).ROLES[role]
            ),
        }
        for role in AGENT_TYPES
    ]


@app.post("/api/agents/{role}/run")
def run_agent(role: str, payload: dict, _admin=Depends(require_admin)):
    if not isinstance(payload, dict) or len(repr(payload).encode("utf-8")) > 10000:
        raise HTTPException(422, "agent payload must be an object no larger than 10 KB")
    if any(not isinstance(key, str) for key in payload):
        raise HTTPException(422, "agent payload keys must be strings")
    try:
        KILL.check()
    except RuntimeError as exc:
        AUDIT.add("agent.run_denied", "human-admin", {"role": role, "reason": "kill_latch_active"})
        raise HTTPException(423, str(exc)) from exc
    if role not in AGENT_TYPES:
        raise HTTPException(404, "unknown agent role")
    task_id = os.urandom(16).hex()
    state = {"role": role, "status": "running"}
    if DB_REPOSITORY is not None:
        DB_REPOSITORY.save_agent_state(task_id, role, state)
    if REDIS_STORE is not None:
        REDIS_STORE.heartbeat(task_id, state, 120)
    try:
        agent = AGENT_FACTORY.create_root(f"admin-invoked-{role}", role)
        result = agent.execute(task_id, payload)
        completed_state = {"role": role, "status": result.status}
        if DB_REPOSITORY is not None:
            DB_REPOSITORY.save_agent_state(task_id, role, completed_state)
        if REDIS_STORE is not None:
            REDIS_STORE.heartbeat(task_id, completed_state, 120)
        AUDIT.add(
            "agent.task_completed",
            role,
            {"task_id": result.task_id, "status": result.status},
        )
        return {
            "agent": result.agent,
            "task_id": result.task_id,
            "status": result.status,
            "output": result.output,
        }
    except DeveloperUnavailable as exc:
        failed_state = {"role": role, "status": "provider_unavailable"}
        if DB_REPOSITORY is not None: DB_REPOSITORY.save_agent_state(task_id, role, failed_state)
        if REDIS_STORE is not None: REDIS_STORE.heartbeat(task_id, failed_state, 120)
        raise HTTPException(503, str(exc)) from exc
    except (Denied, ValueError, RuntimeError) as exc:
        failed_state = {"role": role, "status": "failed"}
        if DB_REPOSITORY is not None: DB_REPOSITORY.save_agent_state(task_id, role, failed_state)
        if REDIS_STORE is not None: REDIS_STORE.heartbeat(task_id, failed_state, 120)
        raise HTTPException(403, str(exc)) from exc


@app.get("/api/tasks")
def list_tasks(_admin=Depends(require_admin)):
    if REDIS_STORE is not None:
        cached = REDIS_STORE.get("tasks:list")
        if cached is not None:
            return cached
    if DB_REPOSITORY is not None:
        result = [{"id": row.id, "goal": row.goal, "status": row.status, "proposal": row.proposal, "created_at": row.created_at.isoformat()} for row in DB_REPOSITORY.list_tasks()]
        if REDIS_STORE is not None: REDIS_STORE.put("tasks:list", result, 15)
        return result
    if FLOW is None:
        return []
    return list(FLOW.items.values())


@app.post("/api/tasks")
def create_task(x: Goal, _admin=Depends(require_admin)):
    if FLOW is None:
        raise HTTPException(503, "approval service is not configured")
    try:
        result = FLOW.create(x.goal)
        if REDIS_STORE is not None: REDIS_STORE.delete("tasks:list")
        return result
    except DeveloperUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(423, str(exc)) from exc
    except Denied as exc:
        raise HTTPException(403, str(exc)) from exc


@app.post("/api/tasks/{pid}/test")
def test_task(pid: str, _admin=Depends(require_admin)):
    if len(pid) != 32 or any(c not in "0123456789abcdef" for c in pid):
        raise HTTPException(404, "unknown proposal")
    if FLOW is None:
        raise HTTPException(503, "workflow is not configured")
    try:
        result = FLOW.test(pid)
        if REDIS_STORE is not None: REDIS_STORE.delete("tasks:list")
        return result
    except KeyError as exc:
        raise HTTPException(404, "unknown proposal") from exc
    except SandboxUnavailable as exc:
        raise HTTPException(
            503, {"code": "sandbox_unavailable", "detail": str(exc)}
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(423, str(exc)) from exc


@app.post("/api/approvals/token/{pid}")
def issue_approval_token(pid: str, _admin=Depends(require_admin)):
    if len(pid) != 32 or any(c not in "0123456789abcdef" for c in pid):
        raise HTTPException(404, "unknown proposal")
    if FLOW is None:
        raise HTTPException(503, "approval service is not configured")
    try:
        return {"token": FLOW.issue_human_token(pid)}
    except KeyError as exc:
        raise HTTPException(404, "unknown proposal") from exc
    except (Denied, RuntimeError) as exc:
        raise HTTPException(403, str(exc)) from exc


@app.post("/api/approvals")
def decide(x: Decision, _admin=Depends(require_admin)):
    if FLOW is None:
        raise HTTPException(503, "approval service is not configured")
    if x.decision not in ("approve", "reject"):
        raise HTTPException(422, "invalid decision")
    try:
        result = FLOW.decide(x.proposal_id, x.decision, x.reason, x.token)
        if REDIS_STORE is not None: REDIS_STORE.delete("tasks:list")
        return result
    except KeyError as exc:
        raise HTTPException(404, "unknown proposal") from exc
    except (Denied, RuntimeError) as exc:
        raise HTTPException(403, str(exc)) from exc


@app.post("/api/kill")
def stop(_admin=Depends(require_admin)):
    KILL.stop()
    AUDIT.add("kill.activated", "human-admin", {})
    return {"status": "stopped"}


@app.post("/api/restart")
def start(_admin=Depends(require_admin)):
    KILL.start()
    AUDIT.add("kill.reset", "human-admin", {})
    return {"status": "running"}


@app.get("/api/audit/verify")
def verify(_admin=Depends(require_admin)):
    return AUDIT.verify()


@app.get("/api/logs")
def logs(_admin=Depends(require_admin)):
    return AUDIT.rows()[-100:]


@app.get("/api/memory")
def read_memory(_admin=Depends(require_admin)):
    if REDIS_STORE is not None:
        cached = REDIS_STORE.get("memory:list")
        if cached is not None:
            return cached
    if DB_REPOSITORY is not None:
        result = [{"kind": row.kind, "text": row.content, "metadata": row.metadata_json, "created_at": row.created_at.isoformat()} for row in DB_REPOSITORY.list_memory()]
    else:
        result = MEMORY.data
    if REDIS_STORE is not None:
        REDIS_STORE.put("memory:list", result, 30)
    return result


class MemoryInput(BaseModel):
    kind: str = "lesson"
    text: str = Field(min_length=1, max_length=1000)


@app.post("/api/memory")
def write_memory(x: MemoryInput, _admin=Depends(require_admin)):
    try:
        record = MEMORY.write(x.kind, x.text)
        if DB_REPOSITORY is not None:
            DB_REPOSITORY.save_memory(record["kind"], record["text"])
        if REDIS_STORE is not None:
            REDIS_STORE.delete("memory:list")
            REDIS_STORE.put("memory:last", record, 3600)
        AUDIT.add("memory.write", "human-admin", {"kind": x.kind})
        return record
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/healthz")
def healthz():
    return {"status":"ok", "control_plane":"reachable", "audit_valid":AUDIT.verify().get("valid", False)}

@app.get("/metrics", response_class=PlainTextResponse)
@app.get("/api/metrics", response_class=PlainTextResponse)
def prometheus_metrics():
    return METRICS.render()

@app.get("/api/monitoring")
def monitoring(_admin=Depends(require_admin)):
    state = status_view()
    if REDIS_STORE is not None:
        depth = REDIS_STORE.queue_depth()
        if depth is not None: METRICS.queue_depth = depth
    checks = {"database": DB_REPOSITORY is not None, "redis": REDIS_STORE is not None, "opa": OPA is not None}
    if DB_REPOSITORY is not None:
        try:
            with DB_REPOSITORY.sessions() as db: db.execute(__import__("sqlalchemy").text("SELECT 1"))
        except Exception: checks["database"] = False
    if REDIS_STORE is not None:
        try: REDIS_STORE.client.ping()
        except Exception: checks["redis"] = False
    if OPA is not None:
        try: OPA.decide({"type":"human","authenticated":True}, "api.access", {"monitoring":True})
        except Exception: checks["opa"] = False
    thresholds = {"cpu_percent": float(os.getenv("ALERT_CPU_PERCENT", "90")), "memory_percent": float(os.getenv("ALERT_MEMORY_PERCENT", "90")), "disk_percent": float(os.getenv("ALERT_DISK_PERCENT", "90"))}
    alerts = [f"{key} threshold exceeded: {value}%" for key, value in state["host"].items() if value is not None and key in thresholds and value >= thresholds[key]]
    alerts += [f"{key} unavailable" for key, healthy in checks.items() if not healthy and os.getenv("CRI_"+key.upper()+"_URL")]
    if alerts: notify("CRI operational alert", "\n".join(alerts))
    return {"host":state["host"],"dependencies":checks,"agents":state["agent_heartbeats"],"alerts":alerts}

@app.get("/", response_class=HTMLResponse)
def home():
    return """<!doctype html><html><meta name=viewport content='width=device-width'><title>CRI Control Plane</title><body style='font:16px system-ui;background:#101827;color:#eee;margin:2rem'><h1>CRI Control Plane</h1><p>Prototype status UI. Authenticate API requests with a Bearer admin token.</p><pre id='out'>Loading status…</pre><script>fetch('/api/status').then(r=>r.json()).then(x=>out.textContent=JSON.stringify(x,null,2)).catch(e=>out.textContent=String(e))</script></body></html>"""

# Versioned REST aliases preserve the existing /api paths during migration.
# WebSocket routes are intentionally excluded; /api/ws remains ticket-protected.
for _route in tuple(app.routes):
    _path = getattr(_route, "path", "")
    _methods = getattr(_route, "methods", None)
    _endpoint = getattr(_route, "endpoint", None)
    if _path.startswith("/api/") and _methods and _endpoint is not None and _methods.intersection({"GET", "POST", "PUT", "PATCH", "DELETE"}):
        app.add_api_route(
            "/v1/" + _path[len("/api/"):],
            _endpoint,
            methods=sorted(_methods),
            dependencies=getattr(_route, "dependencies", None),
            response_model=getattr(_route, "response_model", None),
            include_in_schema=True,
        )
