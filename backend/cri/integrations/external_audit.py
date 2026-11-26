"""Remote audit forwarder. Durability/immutability must be enforced by the receiver."""
import hashlib, hmac, json
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

class ExternalAuditUnavailable(RuntimeError): pass
class ExternalAuditSink:
    def __init__(self, endpoint: str, bearer_token: str, opener=urlopen):
        if not endpoint.startswith("https://"):
            raise ValueError("external audit endpoint must use HTTPS")
        if len(bearer_token) < 32: raise ValueError("audit bearer token too short")
        self.endpoint, self.token, self.opener = endpoint, bearer_token, opener
    def append(self, row: dict):
        canonical = json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        digest = hashlib.sha256(canonical).hexdigest()
        req = Request(self.endpoint, data=canonical, headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json", "Idempotency-Key": digest}, method="POST")
        try:
            with self.opener(req, timeout=3) as response:
                if response.status not in (200, 201, 202, 204): raise ExternalAuditUnavailable("audit sink rejected event")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise ExternalAuditUnavailable("external audit sink unavailable") from exc
        return digest
