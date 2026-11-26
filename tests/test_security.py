from pathlib import Path
import pytest
from cri.core import (
    Audit,
    Denied,
    Kill,
    Policy,
    Sandbox,
    SandboxUnavailable,
    Tokens,
    Workflow,
)


class UnavailableSandbox:
    def run(self, code):
        raise SandboxUnavailable("sandbox not available")


def test_role_cannot_request_extra_scope(tmp_path):
    audit = Audit(tmp_path / "audit.jsonl")
    policy = Policy(audit)
    with pytest.raises(Denied):
        policy.identity("agent", "research", {"sandbox"})


def test_child_permissions_are_intersection_of_parent_and_role(tmp_path):
    policy = Policy(Audit(tmp_path / "audit.jsonl"))
    parent = policy.identity("parent", "research")
    child = policy.child(parent, "child", "developer")
    assert child.scopes == frozenset()


def test_audit_detects_modified_event(tmp_path):
    path = tmp_path / "audit.jsonl"
    audit = Audit(path)
    audit.add("safe.event", "agent", {})
    path.write_text(path.read_text().replace("safe.event", "evil.event"))
    assert audit.verify()["valid"] is False


def test_token_is_bound_to_proposal_and_single_use(tmp_path):
    tokens = Tokens("x" * 32, nonce_db=tmp_path / "nonces.sqlite")
    token = tokens.issue("proposal-a")
    assert not tokens.use(token, "proposal-b")
    assert tokens.use(token, "proposal-a")
    assert not tokens.use(token, "proposal-a")


def test_sandbox_absence_fails_closed():
    sandbox = Sandbox(docker_binary="/path/that/does/not/exist")
    with pytest.raises(SandboxUnavailable):
        sandbox.run("print('must not execute')")


def test_unavailable_sandbox_prevents_approval_token(tmp_path):
    audit = Audit(tmp_path / "audit.jsonl")
    policy = Policy(audit)
    tokens = Tokens("y" * 32, nonce_db=tmp_path / "nonces.sqlite")
    flow = Workflow(
        audit, policy, Kill(tmp_path / "KILL"), tokens, UnavailableSandbox()
    )
    proposal = flow.create("test fail closed")
    with pytest.raises(SandboxUnavailable):
        flow.test(proposal["id"])
    assert flow.items[proposal["id"]]["status"] == "sandbox_unavailable"
    with pytest.raises(Denied):
        flow.issue_human_token(proposal["id"])


def test_kill_switch_blocks_new_workflow_items(tmp_path):
    audit = Audit(tmp_path / "audit.jsonl")
    policy = Policy(audit)
    tokens = Tokens("z" * 32, nonce_db=tmp_path / "nonces.sqlite")
    kill = Kill(tmp_path / "KILL")
    flow = Workflow(audit, policy, kill, tokens, UnavailableSandbox())
    kill.stop()
    with pytest.raises(RuntimeError):
        flow.create("should be blocked")


def test_audit_cli_returns_nonzero_for_tampered_file(tmp_path, monkeypatch):
    from cri.cli import main

    path = tmp_path / "audit.jsonl"
    audit = Audit(path)
    audit.add("valid", "operator", {})
    path.write_text(path.read_text().replace("valid", "tampered"))
    monkeypatch.setenv("CRI_AUDIT_FILE", str(path))
    monkeypatch.setattr("sys.argv", ["cri-audit", "verify"])
    assert main() == 1


def test_local_backup_and_restore_scripts(tmp_path):
    import os
    import subprocess

    root = Path(__file__).resolve().parents[1]
    source = tmp_path / "source-data"
    source.mkdir()
    (source / "audit.jsonl").write_text("sample-audit\n")
    backup_dir = tmp_path / "backups"
    env = dict(os.environ, CRI_DATA_DIR=str(source))
    result = subprocess.run(
        [str(root / "scripts/backup.sh"), str(backup_dir)],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    archive = result.stdout.strip()
    target = tmp_path / "restored-data"
    env = dict(os.environ, CRI_DATA_DIR=str(target), CRI_RESTORE_CONFIRM="YES")
    subprocess.run(
        [str(root / "scripts/restore.sh"), archive],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert (target / "audit.jsonl").read_text() == "sample-audit\n"


def test_sandbox_rejects_mutable_image_tag():
    sandbox = Sandbox(docker_binary="/fake/docker", image="python:3.12-alpine")
    with pytest.raises(SandboxUnavailable, match="sha256 digest"):
        sandbox.run("print('no run')")
