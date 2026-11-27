import asyncio
from types import SimpleNamespace
import pytest

from cri import main

class DummyConnection:
    dialect = SimpleNamespace(name="sqlite")
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def exec_driver_sql(self, query): return SimpleNamespace(scalar=lambda: "tasks")

class DummyEngine:
    def __init__(self): self.disposed = False
    def connect(self): return DummyConnection()
    def dispose(self): self.disposed = True

class DummyRedis:
    def __init__(self): self.closed = False
    def ping(self): return True
    def close(self): self.closed = True

class DummyRepo:
    def __init__(self): self.appended = []
    def append_audit(self, *args): self.appended.append(args)


def prepare(monkeypatch):
    monkeypatch.setattr(main, "ADMIN_TOKEN", "a" * 40)
    monkeypatch.setattr(main, "TOKENS", object())
    monkeypatch.setattr(main, "OPA", None)
    monkeypatch.setattr(main, "DB_REPOSITORY", None)
    monkeypatch.setattr(main, "REDIS_STORE", None)
    monkeypatch.setattr(main.AUDIT, "db_writer", None)
    main.AUDIT.path.write_text("", encoding="utf-8")
    monkeypatch.delenv("CRI_DATABASE_URL", raising=False)
    monkeypatch.delenv("CRI_REDIS_URL", raising=False)


def test_lifespan_runs_without_optional_services(monkeypatch):
    prepare(monkeypatch)
    async def run():
        async with main.lifespan(main.app):
            assert main.DB_REPOSITORY is None
    asyncio.run(run())


def test_lifespan_connects_configured_database_redis_and_opa(monkeypatch):
    prepare(monkeypatch)
    engine, repo, redis_client = DummyEngine(), DummyRepo(), DummyRedis()
    monkeypatch.setenv("CRI_DATABASE_URL", "sqlite:///unused.db")
    monkeypatch.setenv("CRI_REDIS_URL", "redis://unused")
    monkeypatch.setattr(main, "get_engine", lambda url: engine)
    monkeypatch.setattr(main, "session_factory", lambda value: object())
    monkeypatch.setattr(main, "SQLRepository", lambda sessions: repo)
    class OPA:
        def __init__(self): self.calls = 0
        def decide(self, *args): self.calls += 1; return True
    opa = OPA(); monkeypatch.setattr(main, "OPA", opa)
    import sys
    monkeypatch.setitem(sys.modules, "redis", SimpleNamespace(Redis=SimpleNamespace(from_url=lambda *a, **k: redis_client)))
    async def run():
        async with main.lifespan(main.app):
            assert main.DB_REPOSITORY is repo
            assert main.REDIS_STORE is not None
            assert opa.calls == 1
            main.AUDIT.db_writer({"event": "x", "actor": "a", "details": {}, "prev": "0" * 64, "hash": "1" * 64, "time": 123.0})
            assert len(repo.appended) == 1
    asyncio.run(run())
    assert engine.disposed and redis_client.closed


def test_lifespan_rejects_missing_admin_secret(monkeypatch):
    prepare(monkeypatch)
    monkeypatch.setattr(main, "ADMIN_TOKEN", "short")
    async def run():
        async with main.lifespan(main.app): pass
    with pytest.raises(RuntimeError, match="CRI_ADMIN_TOKEN"):
        asyncio.run(run())


def test_lifespan_rejects_missing_approval_secret(monkeypatch):
    prepare(monkeypatch)
    monkeypatch.setattr(main, "TOKENS", None)
    async def run():
        async with main.lifespan(main.app): pass
    with pytest.raises(RuntimeError, match="CRI_APPROVAL_SECRET"):
        asyncio.run(run())
