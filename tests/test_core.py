import pytest
from cri.core import Audit, Policy, Denied, Tokens, Kill, Memory, Workflow


class FakeDeveloper:
    def generate(self, specification, filename="generated_module.py"):
        import hashlib
        content = "def run(context):\n    return {\"ok\": True}\n"
        return type("Draft", (), {"content": content, "filename": filename, "sha256": hashlib.sha256(content.encode()).hexdigest()})()

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
    workflow = Workflow(audit, policy, kill, tokens, FakeSandbox(), FakeDeveloper())
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


def test_approval_token_ttl_must_be_bounded():
    with pytest.raises(ValueError, match="TTL"):
        Tokens("s" * 32, ttl=0)
    with pytest.raises(ValueError, match="TTL"):
        Tokens("s" * 32, ttl=3601)


def test_promoted_proposal_cannot_be_tested_again(tmp_path):
    audit = Audit(tmp_path / "audit.jsonl")
    policy = Policy(audit)
    tokens = Tokens("r" * 32, nonce_db=tmp_path / "nonces.sqlite")
    workflow = Workflow(audit, policy, Kill(tmp_path / "KILL"), tokens, FakeSandbox(), FakeDeveloper())
    proposal = workflow.create("bounded proposal")
    workflow.test(proposal["id"])
    token = workflow.issue_human_token(proposal["id"])
    workflow.decide(proposal["id"], "approve", "reviewed", token)
    with pytest.raises(Denied, match="state"):
        workflow.test(proposal["id"])


def test_approval_reason_is_required(tmp_path):
    audit = Audit(tmp_path / "audit.jsonl")
    policy = Policy(audit)
    tokens = Tokens("r" * 32, nonce_db=tmp_path / "nonces.sqlite")
    workflow = Workflow(audit, policy, Kill(tmp_path / "KILL"), tokens, FakeSandbox(), FakeDeveloper())
    proposal = workflow.create("bounded proposal")
    workflow.test(proposal["id"])
    token = workflow.issue_human_token(proposal["id"])
    with pytest.raises(ValueError, match="reason"):
        workflow.decide(proposal["id"], "approve", "", token)


def test_audit_verify_handles_non_object_json_records(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text('["not", "an", "event"]\n', encoding="utf-8")
    assert Audit(path).verify() == {"valid": False, "count": 0}


def test_audit_verify_rejects_non_finite_numbers(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text('{"event":"x","actor":"a","details":{"n":NaN},"prev":"' + "0" * 64 + '","time":1,"hash":"bad"}\n', encoding="utf-8")
    assert Audit(path).verify() == {"valid": False, "count": 0}
