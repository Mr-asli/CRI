import pytest
from cri.core import Audit, Policy, Denied, Tokens, Kill, Memory, Workflow


class FakeSandbox:
    def run(self, code):
        return {"returncode": 0, "stdout": "ok", "stderr": ""}


def test_audit(tmp_path):
    audit = Audit(str(tmp_path / "audit.jsonl"))
    audit.add("event", "actor", {})
    assert audit.verify()["valid"]
    (tmp_path / "audit.jsonl").write_text("broken", encoding="utf-8")
    assert not audit.verify()["valid"]


def test_policy_and_child_scope_intersection(tmp_path):
    audit = Audit(str(tmp_path / "audit.jsonl"))
    policy = Policy(audit)
    research = policy.identity("researcher", "research")
    with pytest.raises(Denied):
        policy.check(research, "sandbox")
    child = policy.child(research, "child-dev", "developer")
    assert child.scopes == frozenset()
    assert audit.verify()["count"] == 2


def test_token_replay():
    tokens = Tokens("s" * 32)
    token = tokens.issue("abc")
    assert tokens.use(token, "abc")
    assert not tokens.use(token, "abc")
    assert not tokens.use(tokens.issue("other"), "abc")


def test_kill(tmp_path):
    kill = Kill(str(tmp_path / "KILL"))
    kill.stop()
    with pytest.raises(RuntimeError):
        kill.check()
    kill.start()
    kill.check()


def test_memory_guard():
    memory = Memory()
    memory.write("lesson", "prefer deterministic tests")
    with pytest.raises(ValueError):
        memory.write("lesson", "my password is abc")


def test_promotion_requires_separate_human_token(tmp_path):
    audit = Audit(str(tmp_path / "audit.jsonl"))
    policy = Policy(audit)
    kill = Kill(str(tmp_path / "KILL"))
    tokens = Tokens("z" * 32, nonce_db=str(tmp_path / "nonces.sqlite3"))
    workflow = Workflow(audit, policy, kill, tokens, FakeSandbox())
    proposal = workflow.create("sample goal")
    workflow.test(proposal["id"])
    with pytest.raises(Denied):
        workflow.decide(proposal["id"], "approve", "ok", "bad")
    assert workflow.items[proposal["id"]]["status"] == "tested"
    human_token = workflow.issue_human_token(proposal["id"])
    assert (
        workflow.decide(proposal["id"], "approve", "reviewed", human_token)["status"]
        == "promoted"
    )
