import hmac
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

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
from .agents.factory import AGENT_TYPES
from .tools import ToolGateway, ToolSpec
from .integrations.opa import OPAClient, OPAUnavailable, OPADenied, OPAPolicy
from .integrations.redis_store import RedisTTLStore
from .db import get_engine, session_factory, SQLRepository

DATA = os.getenv("CRI_DATA_DIR", "./data")
ADMIN_TOKEN = os.getenv("CRI_ADMIN_TOKEN", "")
APPROVAL_SECRET = os.getenv("CRI_APPROVAL_SECRET", "")
AUDIT = Audit(os.getenv("CRI_AUDIT_FILE", DATA + "/audit.jsonl"))
OPA = OPAClient(os.environ["CRI_OPA_URL"]) if os.getenv("CRI_OPA_URL") else None
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
GATEWAY = ToolGateway(POLICY, AUDIT, KILL)
def _write_memory(payload):
    record = MEMORY.write("lesson", payload["text"])
    if DB_REPOSITORY is not None:
        DB_REPOSITORY.save_memory(record["kind"], record["text"])
    return record

GATEWAY.register(
    ToolSpec("memory.write", "memory_write", frozenset({"memory"}), _write_memory)
)
AGENT_FACTORY = AgentFactory(POLICY, GATEWAY)
DB_REPOSITORY = None
REDIS_STORE = None


@asynccontextmanager
async def lifespan(app):
    global DB_REPOSITORY, REDIS_STORE
    if len(ADMIN_TOKEN.encode()) < 32:
        raise RuntimeError("CRI_ADMIN_TOKEN must be set to at least 32 bytes")
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
                migrated = connection.exec_driver_sql("SELECT to_regclass('public.tasks')").scalar()
                if migrated is None:
                    raise RuntimeError("database schema is not migrated; apply backend/alembic/versions before startup")
        DB_REPOSITORY = SQLRepository(session_factory(engine))
        AUDIT.db_writer = lambda row: DB_REPOSITORY.append_audit(
            row["event"], row["actor"], row["details"], row["prev"], row["hash"]
        )
        if FLOW is not None:
            FLOW.repository = DB_REPOSITORY
        FLOW.restore()

    redis_url = os.getenv("CRI_REDIS_URL")
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
        "sandbox": "configured" if sandbox.docker_binary and "@sha256:" in sandbox.image else "unavailable",
        "execution_guarantee": "not_independently_supervised",
        "database": "connected" if DB_REPOSITORY is not None else "not_configured",
        "redis": "connected" if REDIS_STORE is not None else "not_configured",
        "opa": "configured" if OPA is not None else "not_configured",
        "remote_audit": "configured" if AUDIT.remote_sink is not None else "not_configured",
        "host_watchdog": "deployment_required",
    }


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
    try:
        agent = AGENT_FACTORY.create_root(f"admin-invoked-{role}", role)
        result = agent.execute(os.urandom(8).hex(), payload)
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
    except (Denied, ValueError, RuntimeError) as exc:
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
    if DB_REPOSITORY is not None:
        return [{"kind": row.kind, "text": row.content, "metadata": row.metadata_json, "created_at": row.created_at.isoformat()} for row in DB_REPOSITORY.list_memory()]
    return MEMORY.data


class MemoryInput(BaseModel):
    kind: str = "lesson"
    text: str = Field(min_length=1, max_length=1000)


@app.post("/api/memory")
def write_memory(x: MemoryInput, _admin=Depends(require_admin)):
    try:
        record = MEMORY.write(x.kind, x.text)
        if DB_REPOSITORY is not None:
            DB_REPOSITORY.save_memory(record["kind"], record["text"])
        AUDIT.add("memory.write", "human-admin", {"kind": x.kind})
        return record
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/", response_class=HTMLResponse)
def home():
    return """<!doctype html><html><meta name=viewport content='width=device-width'><title>CRI Control Plane</title><body style='font:16px system-ui;background:#101827;color:#eee;margin:2rem'><h1>CRI Control Plane</h1><p>Prototype status UI. Authenticate API requests with a Bearer admin token.</p><pre id='out'>Loading status…</pre><script>fetch('/api/status').then(r=>r.json()).then(x=>out.textContent=JSON.stringify(x,null,2)).catch(e=>out.textContent=String(e))</script></body></html>"""
