import json
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cri.db.models import Base, TaskRecord
from cri.db.repository import SQLRepository
from cri.integrations.redis_store import RedisTTLStore
from cri.integrations.opa import OPAClient, OPADenied, OPAUnavailable
from cri.integrations.external_audit import ExternalAuditSink
from cri.agents.developer import Developer
from cri.self_improvement import ImprovementWorkflow, Stage

class FakeRedis:
    def __init__(self): self.data = {}
    def setex(self, key, ttl, value): self.data[key] = value
    def get(self, key): return self.data.get(key)
    def delete(self, key): return int(self.data.pop(key, None) is not None)

class FakeResponse:
    status = 200
    def __init__(self, body): self.body = body
    def read(self): return json.dumps(self.body).encode()
    def __enter__(self): return self
    def __exit__(self, *args): return False

def test_sql_repository_persists_task_with_sqlite(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'cri.sqlite'}")
    TaskRecord.__table__.create(engine)
    repo = SQLRepository(sessionmaker(engine, expire_on_commit=False))
    repo.save_task("a" * 32, "demo", "pending", {"v": 1})
    row = repo.get_task("a" * 32)
    assert row.goal == "demo" and row.proposal == {"v": 1}
    assert len(repo.list_tasks()) == 1
    with pytest.raises(ValueError): repo.list_tasks(0)

def test_redis_ttl_store_roundtrip_and_validation():
    client = FakeRedis(); store = RedisTTLStore(client)
    store.put("job", {"state": "queued"}, 60)
    assert store.get("job") == {"state": "queued"}
    assert store.delete("job") and store.get("job") is None
    with pytest.raises(ValueError): store.put("", {}, 60)

def test_opa_client_allow_and_deny():
    allow = OPAClient("http://opa:8181", opener=lambda *a, **k: FakeResponse({"result": True}))
    assert allow.decide({"type": "human"}, "api.access")
    deny = OPAClient("http://opa:8181", opener=lambda *a, **k: FakeResponse({"result": False}))
    with pytest.raises(OPADenied): deny.decide({}, "system.restart")

def test_opa_client_fails_closed_on_unavailable():
    def broken(*args, **kwargs): raise OSError("offline")
    client = OPAClient("https://opa.example", opener=broken)
    with pytest.raises(OPAUnavailable): client.decide({}, "api.access")

def test_external_audit_sink_requires_https_and_posts():
    seen = {}
    def opener(request, timeout):
        seen["request"] = request; seen["timeout"] = timeout
        return FakeResponse({})
    sink = ExternalAuditSink("https://audit.example/events", "x" * 32, opener=opener)
    digest = sink.append({"hash": "a" * 64, "event": "stop"})
    assert len(digest) == 64 and seen["request"].get_method() == "POST"
    with pytest.raises(ValueError): ExternalAuditSink("http://bad", "x" * 32)

def test_developer_generates_reviewable_draft_without_execution():
    response = FakeResponse({"choices": [{"message": {"content": "def parse(value):\n    return str(value)\n"}}]})
    developer = Developer("https://llm.example/v1", "k" * 32, "test-model", opener=lambda *a, **k: response)
    draft = developer.generate("write a small parser")
    compile(draft.content, draft.filename, "exec")
    assert draft.status == "draft_only" and len(draft.sha256) == 64
    with pytest.raises(ValueError): developer.generate("hello", "../escape.py")
    with pytest.raises(RuntimeError, match="not configured"):
        Developer().generate("write code")

def test_improvement_workflow_requires_evidence_and_human_approval(tmp_path):
    from cri.core import Audit
    from cri.core import Tokens
    flow = ImprovementWorkflow(Audit(tmp_path / "audit.jsonl"), Tokens("k" * 32, nonce_db=tmp_path / "improve-nonces.sqlite"))
    item = flow.create("improve parser")
    item = flow.advance(item.id, {"proposal": "draft"})
    item = flow.advance(item.id, {"passed": True})
    with pytest.raises(PermissionError): flow.advance(item.id, {})
    item = flow.advance(item.id, {"sandbox_completed": True})
    item = flow.advance(item.id, {"test_run": "passed"})
    item = flow.advance(item.id, {"tests_passed": True, "baseline_compared": True})
    item = flow.advance(item.id, {"human_review": "signed"})
    with pytest.raises(PermissionError): flow.advance(item.id, {}, approval_token="missing")
    token = flow.issue_human_approval(item.id)
    item = flow.advance(item.id, {"human_token_verified": True}, approval_token=token)
    with pytest.raises(ValueError): flow.advance(item.id, {})
    assert item.stage == Stage.PROMOTE

def test_database_engine_factory_and_session_factory(tmp_path):
    from cri.db.session import get_engine, session_factory
    url = f"sqlite:///{tmp_path / 'engine.sqlite'}"
    get_engine.cache_clear()
    engine = get_engine(url)
    assert engine.dialect.name == "sqlite"
    factory = session_factory(engine)
    with factory() as session:
        assert session.execute(__import__("sqlalchemy").text("SELECT 1")).scalar() == 1
    get_engine.cache_clear()
    engine.dispose()

def test_database_engine_requires_url(monkeypatch):
    from cri.db.session import get_engine
    monkeypatch.delenv("CRI_DATABASE_URL", raising=False)
    get_engine.cache_clear()
    with pytest.raises(RuntimeError, match="CRI_DATABASE_URL"):
        get_engine()
    get_engine.cache_clear()

def test_repository_updates_task_and_saves_memory_audit(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from cri.db.models import TaskRecord, MemoryRecord, AuditRecord
    from cri.db.repository import SQLRepository
    engine = create_engine(f"sqlite:///{tmp_path / 'repo.sqlite'}")
    for table in (TaskRecord.__table__, MemoryRecord.__table__, AuditRecord.__table__):
        table.create(engine)
    repo = SQLRepository(sessionmaker(engine, expire_on_commit=False))
    repo.save_task("b" * 32, "first", "pending")
    repo.save_task("b" * 32, "updated", "tested", {"ok": True})
    assert repo.get_task("b" * 32).goal == "updated"
    memory = repo.save_memory("lesson", "small durable note")
    audit = repo.append_audit("started", "tester", {}, "0" * 64, "1" * 64)
    assert memory.content == "small durable note" and audit.event == "started"
    engine.dispose()

def test_pgvector_repository_rejects_bad_vectors_before_database_access(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'vector.sqlite'}")
    repo = SQLRepository(sessionmaker(engine))
    with pytest.raises(ValueError, match="1536"):
        repo.save_embedding("m" * 32, [0.1, 0.2])
    with pytest.raises(ValueError, match="1536"):
        repo.nearest_memories([float("nan")] * 1536)
    with pytest.raises(ValueError, match="limit"):
        repo.nearest_memories([0.1] * 1536, 0)
    engine.dispose()

def test_opa_policy_wraps_local_role_check_and_external_decision(tmp_path):
    from cri.core import Audit, Policy, Denied
    from cri.integrations.opa import OPAPolicy
    class AllowClient:
        def __init__(self): self.calls = []
        def decide(self, *args): self.calls.append(args); return True
    audit = Audit(tmp_path / "opa-policy.jsonl")
    client = AllowClient(); policy = OPAPolicy(Policy(audit), client)
    identity = policy.identity("dev", "developer")
    policy.check(identity, "propose")
    assert client.calls[0][1] == "propose"
    with pytest.raises(Denied): policy.check(identity, "memory_write")

def test_redis_queue_and_agent_heartbeat_primitives():
    class QueueRedis(FakeRedis):
        def __init__(self): super().__init__(); self.queues = {}
        def rpush(self, key, value): self.queues.setdefault(key, []).append(value)
        def ltrim(self, key, start, end): self.queues[key] = self.queues.get(key, [])[start:]
        def llen(self, key): return len(self.queues.get(key, []))
        def blpop(self, key, timeout=0):
            values = self.queues.get(key, [])
            return (key, values.pop(0).encode()) if values else None
    redis = QueueRedis(); store = RedisTTLStore(redis)
    assert store.enqueue("jobs", {"id": "1"}) == 1
    assert store.dequeue("jobs") == {"id": "1"}
    store.heartbeat("dev-1", {"status": "working"}, 30)
    assert store.agent_state("dev-1")["status"] == "working"
    with pytest.raises(ValueError): store.dequeue("jobs", timeout=60)


def test_repository_persists_improvements_agents_and_audit_status(tmp_path):
    from cri.db.models import Base
    engine = create_engine(f"sqlite:///{tmp_path / 'state.sqlite'}")
    Base.metadata.create_all(engine)
    repo = SQLRepository(sessionmaker(engine, expire_on_commit=False))
    repo.save_improvement("c" * 32, "review proposal", "proposal", {"ok": True})
    assert repo.list_improvements()[0].stage == "proposal"
    repo.save_agent_state("developer-1", "developer", {"status": "idle"})
    assert repo.get_agent_state("developer-1").state["status"] == "idle"
    import hashlib
    event_time = 123.5
    body = {"event": "event", "actor": "actor", "details": {}, "prev": "0" * 64, "time": event_time}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    repo.append_audit("event", "actor", {}, "0" * 64, digest, event_time)
    # Idempotent replay returns the same row rather than inserting duplicates.
    repo.append_audit("event", "actor", {}, "0" * 64, digest, event_time)
    assert repo.audit_status()["count"] == 1
    assert repo.audit_status()["valid"] is True
    engine.dispose()


def test_developer_rejects_bad_provider_response_and_insecure_endpoint():
    from cri.agents.developer import DeveloperUnavailable
    bad = FakeResponse({"choices": []})
    developer = Developer("https://llm.example", "k" * 32, "m", opener=lambda *a, **k: bad)
    with pytest.raises(DeveloperUnavailable): developer.generate("make module")
    with pytest.raises(ValueError, match="HTTPS"):
        Developer("http://llm.example", "k" * 32, "m").generate("make module")

def test_improvement_workflow_restores_durable_stage(tmp_path):
    from cri.core import Audit, Tokens
    from cri.db.models import Base
    engine = create_engine(f"sqlite:///{tmp_path / 'improvements.sqlite'}")
    Base.metadata.create_all(engine)
    repo = SQLRepository(sessionmaker(engine, expire_on_commit=False))
    tokens = Tokens("s" * 32, nonce_db=tmp_path / "improve-state.sqlite")
    flow = ImprovementWorkflow(Audit(tmp_path / "improve-audit.jsonl"), tokens, repo)
    item = flow.create("review persistence")
    flow.advance(item.id, {"proposal": "draft"})
    restored = ImprovementWorkflow(Audit(tmp_path / "restore-audit.jsonl"), tokens, repo)
    assert restored.items[item.id].stage == Stage.PROPOSAL
    engine.dispose()


def test_developer_provider_failures_are_logged_safely(caplog):
    import logging
    from urllib.error import HTTPError, URLError
    from cri.agents.developer import DeveloperUnavailable

    failures = [
        (
            HTTPError(
                "https://llm.example",
                401,
                "unauthorized",
                None,
                None
            ),
            "LLM provider HTTP failure: status=401",
        ),
        (
            URLError("SENSITIVE_CONNECTION_DETAIL"),
            "LLM provider connection failure",
        ),
        (
            TimeoutError("SENSITIVE_TIMEOUT_DETAIL"),
            "LLM provider failure: type=TimeoutError",
        ),
        (
            OSError("SENSITIVE_SOCKET_DETAIL"),
            "LLM provider failure: type=OSError",
        ),
        (
            ValueError("SENSITIVE_RESPONSE_DETAIL"),
            "LLM provider failure: type=ValueError",
        ),
    ]

    for failure, expected_log in failures:
        caplog.clear()

        def broken_opener(*args, **kwargs):
            raise failure

        developer = Developer(
            "https://llm.example/v1",
            "k" * 32,
            "test-model",
            opener=broken_opener,
        )

        with pytest.raises(
            DeveloperUnavailable,
            match="configured LLM provider failed"
        ):
            developer.generate("create a simple module")

        assert expected_log in caplog.text
        assert "SENSITIVE_" not in caplog.text

    assert "cri.llm" in caplog.text or any(
        record.name == "cri.llm" for record in caplog.records
    )
