from pathlib import Path
import pytest
from cri.core import Audit, Denied, Policy, Tokens


def test_audit_chain_rejects_deleted_middle_record(tmp_path: Path):
    path = tmp_path / 'audit.jsonl'
    audit = Audit(path)
    audit.add('one', 'human', {})
    audit.add('two', 'human', {})
    audit.add('three', 'human', {})
    lines = path.read_text().splitlines()
    path.write_text(lines[0] + '\n' + lines[2] + '\n')
    assert audit.verify()['valid'] is False


def test_policy_deny_by_default_for_unknown_action(tmp_path: Path):
    policy = Policy(Audit(tmp_path / 'audit.jsonl'))
    identity = policy.identity('read-only', 'research')
    with pytest.raises(Denied):
        policy.check(identity, 'admin')


def test_expired_approval_token_is_rejected(tmp_path: Path):
    tokens = Tokens('q' * 32, ttl=-1, nonce_db=tmp_path / 'nonce.sqlite')
    token = tokens.issue('proposal')
    assert tokens.use(token, 'proposal') is False
