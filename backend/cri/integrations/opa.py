"""Fail-closed HTTP client for Open Policy Agent."""
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

class OPADenied(PermissionError): pass
class OPAUnavailable(RuntimeError): pass

class OPAClient:
    def __init__(self, endpoint: str, timeout: float = 2.0, opener=urlopen):
        if not endpoint.startswith("http://") and not endpoint.startswith("https://"):
            raise ValueError("OPA endpoint must be HTTP(S)")
        self.endpoint = endpoint.rstrip("/")
        self.timeout, self.opener = timeout, opener

    def decide(self, subject: dict, action: str, resource: dict | None = None) -> bool:
        payload = json.dumps({"input": {"subject": subject, "action": action, "resource": resource or {}}}).encode()
        request = Request(self.endpoint + "/v1/data/cri/authz/allow", data=payload, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with self.opener(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            raise OPAUnavailable("OPA decision service unavailable; request denied") from exc
        result = body.get("result")
        if result is not True:
            raise OPADenied("OPA policy denied action")
        return True

class OPAPolicy:
    """Wraps the local role/scope policy with an external OPA decision point."""
    def __init__(self, local_policy, client: OPAClient):
        self.local_policy, self.client = local_policy, client
    def identity(self, *args, **kwargs):
        return self.local_policy.identity(*args, **kwargs)
    def child(self, *args, **kwargs):
        return self.local_policy.child(*args, **kwargs)
    def check(self, who, action):
        self.local_policy.check(who, action)
        self.client.decide({"type": "agent", "role": who.role, "name": who.name, "scopes": sorted(who.scopes)}, action, {})
