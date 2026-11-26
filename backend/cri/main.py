import hmac
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .core import Audit, Denied, Kill, Memory, Policy, Sandbox, SandboxUnavailable, Tokens, Workflow
from .agents import AgentFactory
from .agents.factory import AGENT_TYPES
from .tools import ToolGateway, ToolSpec

DATA = os.getenv("CRI_DATA_DIR", "./data")
ADMIN_TOKEN = os.getenv("CRI_ADMIN_TOKEN", "")
APPROVAL_SECRET = os.getenv("CRI_APPROVAL_SECRET", "")
AUDIT = Audit(os.getenv("CRI_AUDIT_FILE", DATA + "/audit.jsonl"))
POLICY = Policy(AUDIT)
KILL = Kill(os.getenv("CRI_KILL_FILE", DATA + "/KILL"))
MEMORY = Memory()
TOKENS = Tokens(APPROVAL_SECRET, nonce_db=os.getenv("CRI_NONCE_DB", DATA + "/approval_nonces.sqlite3")) if len(APPROVAL_SECRET.encode()) >= 32 else None
FLOW = Workflow(AUDIT, POLICY, KILL, TOKENS, Sandbox()) if TOKENS else None
GATEWAY = ToolGateway(POLICY, AUDIT, KILL)
GATEWAY.register(ToolSpec("memory.write", "memory_write", frozenset({"memory"}), lambda payload: MEMORY.write("lesson", payload["text"])))
AGENT_FACTORY = AgentFactory(POLICY, GATEWAY)


@asynccontextmanager
async def lifespan(app):
    if len(ADMIN_TOKEN.encode()) < 32:
        raise RuntimeError("CRI_ADMIN_TOKEN must be set to at least 32 bytes")
    if TOKENS is None:
        raise RuntimeError("CRI_APPROVAL_SECRET must be set to at least 32 bytes")
    yield


app = FastAPI(title="CRI Control Plane", version="0.2.0", lifespan=lifespan)


class Goal(BaseModel):
    goal: str = Field(min_length=3, max_length=1000)


class Decision(BaseModel):
    proposal_id: str = Field(min_length=32, max_length=64)
    decision: str
    reason: str = Field(min_length=3, max_length=500)
    token: str = Field(min_length=20, max_length=2048)


def require_admin(authorization: str | None = Header(default=None)):
    if not ADMIN_TOKEN or len(ADMIN_TOKEN.encode()) < 32:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="admin authentication is not configured")
    scheme, _, supplied = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not supplied or not hmac.compare_digest(supplied, ADMIN_TOKEN):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required", headers={"WWW-Authenticate": "Bearer"})
    return "human-admin"


@app.get("/api/status")
def status_view():
    return {"status": "stopped" if KILL.active() else "running", "audit": AUDIT.verify(), "sandbox": "configured" if Sandbox().docker_binary else "unavailable"}


@app.get("/api/agents")
def agents():
    return [{"name": role, "role": role, "implemented": True, "status": "available_not_running", "capabilities": sorted(__import__("cri.core", fromlist=["ROLES"]).ROLES[role])} for role in AGENT_TYPES]


@app.post("/api/agents/{role}/run")
def run_agent(role: str, payload: dict, _admin=Depends(require_admin)):
    if role not in AGENT_TYPES:
        raise HTTPException(404, "unknown agent role")
    try:
        agent = AGENT_FACTORY.create_root(f"admin-invoked-{role}", role)
        result = agent.execute(os.urandom(8).hex(), payload)
        AUDIT.add("agent.task_completed", role, {"task_id": result.task_id, "status": result.status})
        return {"agent": result.agent, "task_id": result.task_id, "status": result.status, "output": result.output}
    except (Denied, ValueError, RuntimeError) as exc:
        raise HTTPException(403, str(exc)) from exc


@app.post("/api/tasks")
def create_task(x: Goal, _admin=Depends(require_admin)):
    if FLOW is None:
        raise HTTPException(503, "approval service is not configured")
    try:
        return FLOW.create(x.goal)
    except RuntimeError as exc:
        raise HTTPException(423, str(exc)) from exc
    except Denied as exc:
        raise HTTPException(403, str(exc)) from exc


@app.post("/api/tasks/{pid}/test")
def test_task(pid: str, _admin=Depends(require_admin)):
    if FLOW is None:
        raise HTTPException(503, "workflow is not configured")
    try:
        return FLOW.test(pid)
    except KeyError as exc:
        raise HTTPException(404, "unknown proposal") from exc
    except SandboxUnavailable as exc:
        raise HTTPException(503, {"code": "sandbox_unavailable", "detail": str(exc)}) from exc
    except RuntimeError as exc:
        raise HTTPException(423, str(exc)) from exc


@app.post("/api/approvals/token/{pid}")
def issue_approval_token(pid: str, _admin=Depends(require_admin)):
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
        return FLOW.decide(x.proposal_id, x.decision, x.reason, x.token)
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
    return MEMORY.data


class MemoryInput(BaseModel):
    kind: str = "lesson"
    text: str = Field(min_length=1, max_length=1000)


@app.post("/api/memory")
def write_memory(x: MemoryInput, _admin=Depends(require_admin)):
    try:
        record = MEMORY.write(x.kind, x.text)
        AUDIT.add("memory.write", "human-admin", {"kind": x.kind})
        return record
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/", response_class=HTMLResponse)
def home():
    return """<!doctype html><html><meta name=viewport content='width=device-width'><title>CRI Control Plane</title><body style='font:16px system-ui;background:#101827;color:#eee;margin:2rem'><h1>CRI Control Plane</h1><p>Prototype status UI. Authenticate API requests with a Bearer admin token.</p><pre id='out'>Loading status…</pre><script>fetch('/api/status').then(r=>r.json()).then(x=>out.textContent=JSON.stringify(x,null,2)).catch(e=>out.textContent=String(e))</script></body></html>"""
