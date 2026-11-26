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
        self.remote_sink = None
        self.db_writer = None
        remote_url = os.getenv("CRI_AUDIT_REMOTE_URL")
        remote_token = os.getenv("CRI_AUDIT_REMOTE_TOKEN", "")
        if remote_url:
            from .integrations.external_audit import ExternalAuditSink
            self.remote_sink = ExternalAuditSink(remote_url, remote_token)

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
            if self.remote_sink is not None:
                # Local chain remains available for diagnosis; remote sink failure
                # is surfaced so the caller can fail closed before proceeding.
                self.remote_sink.append(row)
            if self.db_writer is not None:
                self.db_writer(row)
            return row

    def verify(self):
        previous = ZERO_HASH
        try:
            rows = self.rows()
        except (OSError, ValueError, TypeError, AttributeError, json.JSONDecodeError):
            return {"valid": False, "count": 0}
        for index, original in enumerate(rows):
            if not isinstance(original, dict):
                return {"valid": False, "count": index}
            row = dict(original)
            digest = row.pop("hash", None)
            try:
                expected = hashlib.sha256(
                    json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
                ).hexdigest()
            except (TypeError, ValueError):
                return {"valid": False, "count": index}
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
        if not isinstance(ttl, int) or ttl < 1 or ttl > 3600:
            raise ValueError("approval token TTL must be between 1 and 3600 seconds")
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
            if not isinstance(nonce, str) or len(nonce) != 32:
                return False
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

    def __init__(self, docker_binary=None, image=None):
        self.docker_binary = docker_binary or shutil.which("docker")
        # Mutable tags are deliberately rejected: the runner must use an image
        # pinned by immutable sha256 digest and preloaded by the host operator.
        self.image = image or os.getenv("CRI_SANDBOX_IMAGE", "")

    def run(self, code):
        if not isinstance(code, str) or not code.strip() or len(code.encode("utf-8")) > 5000:
            raise ValueError("source must be non-empty UTF-8 text no larger than 5000 bytes")
        if not self.docker_binary:
            raise SandboxUnavailable("Docker CLI unavailable; execution denied")
        digest = self.image.rsplit("@sha256:", 1)[-1] if "@sha256:" in self.image else ""
        repository = self.image.rsplit("@sha256:", 1)[0] if digest else ""
        if not repository or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest.lower()):
            raise SandboxUnavailable("sandbox image must be pinned by immutable sha256 digest; execution denied")
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
                "--pull=never",
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
        self.repository = None

    def _persist(self, proposal):
        if self.repository is not None:
            # Persist the complete reviewable proposal so API restarts do not
            # leave database tasks that cannot be tested or approved.
            data = {
                "filename": proposal.get("filename"),
                "code_sha256": proposal.get("code_sha256"),
                "code": proposal.get("code"),
                "test": proposal.get("test"),
            }
            self.repository.save_task(
                proposal["id"], proposal["goal"], proposal["status"], data
            )

    def restore(self):
        """Rehydrate workflow state from durable storage during API startup."""
        if self.repository is None:
            return 0
        restored = 0
        list_tasks = getattr(self.repository, "list_tasks", None)
        if not callable(list_tasks):
            return 0
        for row in list_tasks(limit=500):
            data = row.proposal or {}
            code = data.get("code")
            if not isinstance(code, str) or not code:
                # Legacy rows without source are visible but cannot be executed.
                continue
            self.items[row.id] = {
                "id": row.id,
                "goal": row.goal,
                "filename": data.get("filename", "proposal.py"),
                "code_sha256": data.get("code_sha256"),
                "code": code,
                "status": row.status,
                "test": data.get("test"),
            }
            restored += 1
        return restored

    def create(self, goal):
        self.k.check()
        self.p.check(self.p.identity("master", "master"), "propose")
        pid = uuid.uuid4().hex
        from .agents.developer import Developer
        draft = Developer().generate(goal)
        code = draft.content
        self.items[pid] = {
            "id": pid,
            "goal": goal,
            "filename": draft.filename,
            "code_sha256": draft.sha256,
            "code": code,
            "status": "pending",
            "test": None,
        }
        self.a.add("proposal.created", "master", {"id": pid})
        self._persist(self.items[pid])
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
        if proposal["status"] not in ("pending", "failed", "sandbox_unavailable"):
            raise Denied("proposal state does not permit testing")
        try:
            result = self.s.run(proposal["code"])
        except SandboxUnavailable as exc:
            proposal["status"] = "sandbox_unavailable"
            proposal["test"] = {"error": str(exc)}
            self.a.add(
                "sandbox.unavailable", "testing", {"id": pid, "reason": str(exc)}
            )
            self._persist(proposal)
            raise
        except Exception as exc:
            proposal["status"] = "failed"
            proposal["test"] = {"error": str(exc)}
            self.a.add("test.failed", "testing", {"id": pid, "reason": str(exc)})
            self._persist(proposal)
            raise
        proposal["test"] = result
        proposal["status"] = "tested" if result["returncode"] == 0 else "failed"
        self.a.add(
            "test.finished", "testing", {"id": pid, "status": proposal["status"]}
        )
        self._persist(proposal)
        return result

    def decide(self, pid, decision, reason, token):
        self.k.check()
        proposal = self.items[pid]
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
            raise ValueError("approval reason must contain 1 to 500 characters")
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
        self._persist(proposal)
        return proposal
