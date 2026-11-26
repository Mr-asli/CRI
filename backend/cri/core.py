import base64
import hashlib
import hmac
import json
import os
import secrets
import shutil
import sqlite3
import subprocess
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

ROLES = {
    "master": {"plan", "propose"},
    "developer": {"propose", "sandbox"},
    "research": {"memory_read"},
    "testing": {"sandbox"},
    "auditor": {"audit_read"},
    "memory": {"memory_read", "memory_write"},
}
ZERO_HASH = "0" * 64


class Denied(PermissionError):
    pass


class SandboxUnavailable(RuntimeError):
    pass


class Audit:
    """Local tamper-evident JSONL audit. Not a substitute for external WORM storage."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    @contextmanager
    def _locked(self):
        import fcntl

        with self.lock_path.open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def rows(self):
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line:
                rows.append(json.loads(line))
        return rows

    def add(self, event, actor, details):
        if (
            not isinstance(event, str)
            or not isinstance(actor, str)
            or not isinstance(details, dict)
        ):
            raise ValueError("invalid audit event")
        with self._locked():
            rows = self.rows()
            body = {
                "event": event,
                "actor": actor,
                "details": details,
                "prev": rows[-1]["hash"] if rows else ZERO_HASH,
                "time": time.time(),
            }
            digest = hashlib.sha256(
                json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            row = {**body, "hash": digest}
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                )
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
            return row

    def verify(self):
        previous = ZERO_HASH
        try:
            rows = self.rows()
        except (OSError, ValueError, TypeError, AttributeError, json.JSONDecodeError):
            return {"valid": False, "count": 0}
        for index, original in enumerate(rows):
            row = dict(original)
            digest = row.pop("hash", None)
            expected = hashlib.sha256(
                json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            if (
                row.get("prev") != previous
                or not isinstance(digest, str)
                or not hmac.compare_digest(expected, digest)
            ):
                return {"valid": False, "count": index}
            previous = digest
        return {"valid": True, "count": len(rows)}


@dataclass(frozen=True)
class Identity:
    name: str
    role: str
    scopes: frozenset


class Policy:
    """In-process deny-by-default policy prototype; external policy authority remains a deployment requirement."""

    def __init__(self, audit):
        self.audit = audit

    def identity(self, name, role, scopes=None):
        if role not in ROLES:
            raise Denied("unknown role")
        allowed = frozenset(ROLES[role])
        requested = allowed if scopes is None else frozenset(scopes)
        if not requested.issubset(allowed):
            self.audit.add(
                "identity.denied",
                name,
                {"role": role, "reason": "role_scope_escalation"},
            )
            raise Denied("identity scope escalation")
        return Identity(name, role, requested)

    def check(self, who, action):
        ok = action in ROLES.get(who.role, set()) and action in who.scopes
        self.audit.add(
            "policy.allow" if ok else "policy.deny", who.name, {"action": action}
        )
        if not ok:
            raise Denied("action denied")

    def child(self, parent, name, role):
        if role not in ROLES:
            self.audit.add("child.denied", parent.name, {"child": name, "role": role})
            raise Denied("unknown child role")
        scopes = frozenset(ROLES[role]).intersection(parent.scopes)
        child = Identity(name, role, scopes)
        self.audit.add(
            "child.created",
            parent.name,
            {"child": name, "role": role, "scopes": sorted(scopes)},
        )
        return child


class Kill:
    """File-backed stop latch; independent watchdog/process supervisor is not implemented here."""

    def __init__(self, path):
        self.path = Path(path)

    def active(self):
        return self.path.exists()

    def stop(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text("STOP", encoding="utf-8")
        os.replace(temporary, self.path)

    def start(self):
        self.path.unlink(missing_ok=True)

    def check(self):
        if self.active():
            raise RuntimeError("kill switch active")


class Tokens:
    """HMAC approval tokens with durable one-time nonce consumption in SQLite."""

    def __init__(self, secret, ttl=300, nonce_db="./data/approval_nonces.sqlite3"):
        if not isinstance(secret, str) or len(secret.encode()) < 32:
            raise ValueError("CRI_APPROVAL_SECRET must contain at least 32 bytes")
        self.secret = secret.encode()
        self.ttl = ttl
        self.nonce_db = str(nonce_db)
        Path(self.nonce_db).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS used_nonces (nonce TEXT PRIMARY KEY, expires_at INTEGER NOT NULL)"
            )

    def _connect(self):
        db = sqlite3.connect(self.nonce_db, timeout=10, isolation_level="IMMEDIATE")
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def issue(self, pid):
        payload = json.dumps(
            {
                "pid": pid,
                "exp": int(time.time()) + self.ttl,
                "n": secrets.token_hex(16),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        signature = (
            hmac.new(self.secret, payload, hashlib.sha256).hexdigest().encode("ascii")
        )
        return base64.urlsafe_b64encode(payload + b"." + signature).decode()

    def use(self, token, pid):
        try:
            decoded = base64.urlsafe_b64decode(token.encode())
            payload, signature = decoded.rsplit(b".", 1)
            expected = (
                hmac.new(self.secret, payload, hashlib.sha256)
                .hexdigest()
                .encode("ascii")
            )
            if not hmac.compare_digest(signature, expected):
                return False
            data = json.loads(payload)
            now = int(time.time())
            if (
                data.get("pid") != pid
                or not isinstance(data.get("exp"), int)
                or data["exp"] < now
            ):
                return False
            nonce = data["n"]
            with self._connect() as db:
                db.execute("DELETE FROM used_nonces WHERE expires_at < ?", (now,))
                try:
                    db.execute(
                        "INSERT INTO used_nonces(nonce, expires_at) VALUES (?, ?)",
                        (nonce, data["exp"]),
                    )
                except sqlite3.IntegrityError:
                    return False
            return True
        except (ValueError, TypeError, KeyError, json.JSONDecodeError, sqlite3.Error):
            return False


class Sandbox:
    """Docker runner with strict preflight. No Docker socket is mounted into the API service."""

    def __init__(self, docker_binary=None, image="python:3.12-alpine"):
        self.docker_binary = docker_binary or shutil.which("docker")
        self.image = image

    def run(self, code):
        if not isinstance(code, str) or len(code) > 5000:
            raise ValueError("source too large or invalid")
        if not self.docker_binary:
            raise SandboxUnavailable("Docker CLI unavailable; execution denied")
        try:
            health = subprocess.run(
                [self.docker_binary, "info"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SandboxUnavailable(
                f"Docker Engine health check failed: {exc}"
            ) from exc
        if health.returncode != 0:
            raise SandboxUnavailable("Docker Engine unavailable; execution denied")
        with tempfile.TemporaryDirectory(prefix="cri-sandbox-") as directory:
            source = Path(directory, "main.py")
            source.write_text(code, encoding="utf-8")
            os.chmod(directory, 0o755)
            os.chmod(source, 0o444)
            command = [
                self.docker_binary,
                "run",
                "--rm",
                "--network=none",
                "--read-only",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--pids-limit=24",
                "--memory=96m",
                "--cpus=.4",
                "--user=65534:65534",
                "--security-opt=seccomp=default",
                "--mount",
                f"type=bind,src={directory},dst=/src,readonly",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=16m",
                "-w",
                "/src",
                self.image,
                "python",
                "main.py",
            ]
            try:
                result = subprocess.run(
                    command, capture_output=True, text=True, timeout=12, check=False
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("sandbox execution timed out") from exc
            return {
                "returncode": result.returncode,
                "stdout": result.stdout[:8000],
                "stderr": result.stderr[:2000],
            }


class Memory:
    def __init__(self):
        self.data = []

    def write(self, kind, text):
        import re

        if (
            kind not in ("lesson", "result", "project")
            or not isinstance(text, str)
            or len(text) > 1000
            or re.search(
                r"password|secret|api.?key|security policy|permission|scope\s*=",
                text,
                re.I,
            )
        ):
            raise ValueError("unsafe memory")
        record = {"kind": kind, "text": text}
        self.data.append(record)
        return record


class Workflow:
    def __init__(self, audit, policy, kill, tokens, sandbox):
        self.a, self.p, self.k, self.t, self.s = audit, policy, kill, tokens, sandbox
        self.items = {}

    def create(self, goal):
        self.k.check()
        self.p.check(self.p.identity("master", "master"), "propose")
        pid = uuid.uuid4().hex
        code = "print('CRI sandbox check passed')\n"
        self.items[pid] = {
            "id": pid,
            "goal": goal,
            "code": code,
            "status": "pending",
            "test": None,
        }
        self.a.add("proposal.created", "master", {"id": pid})
        return dict(self.items[pid])

    def issue_human_token(self, pid):
        self.k.check()
        proposal = self.items[pid]
        if proposal["status"] != "tested":
            raise Denied("only tested proposals can request human approval")
        token = self.t.issue(pid)
        self.a.add("approval.token_issued", "human", {"id": pid})
        return token

    def test(self, pid):
        self.k.check()
        proposal = self.items[pid]
        try:
            result = self.s.run(proposal["code"])
        except SandboxUnavailable as exc:
            proposal["status"] = "sandbox_unavailable"
            proposal["test"] = {"error": str(exc)}
            self.a.add(
                "sandbox.unavailable", "testing", {"id": pid, "reason": str(exc)}
            )
            raise
        except Exception as exc:
            proposal["status"] = "failed"
            proposal["test"] = {"error": str(exc)}
            self.a.add("test.failed", "testing", {"id": pid, "reason": str(exc)})
            raise
        proposal["test"] = result
        proposal["status"] = "tested" if result["returncode"] == 0 else "failed"
        self.a.add(
            "test.finished", "testing", {"id": pid, "status": proposal["status"]}
        )
        return result

    def decide(self, pid, decision, reason, token):
        self.k.check()
        proposal = self.items[pid]
        if (
            proposal["status"] != "tested"
            or decision not in ("approve", "reject")
            or not self.t.use(token, pid)
        ):
            self.a.add("approval.denied", "human", {"id": pid})
            raise Denied("valid tested approval token required")
        proposal["status"] = "promoted" if decision == "approve" else "rejected"
        self.a.add(
            "approval.decision",
            "human",
            {"id": pid, "decision": decision, "reason": reason},
        )
        return proposal
