"""Policy-gated tool execution. Agents never receive shell or host filesystem primitives."""

from dataclasses import dataclass
from typing import Any, Callable
from cri.core import Audit, Denied, Identity, Kill, Policy


@dataclass(frozen=True)
class ToolSpec:
    name: str
    action: str
    resources: frozenset[str]
    handler: Callable[[dict[str, Any]], Any]


class ToolGateway:
    def __init__(self, policy: Policy, audit: Audit, kill: Kill):
        self.policy, self.audit, self.kill = policy, audit, kill
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if not spec.name or spec.name in self._tools or not callable(spec.handler):
            raise ValueError("invalid or duplicate tool")
        self._tools[spec.name] = spec

    def invoke(
        self, identity: Identity, name: str, resource: str, payload: dict[str, Any]
    ) -> Any:
        self.kill.check()
        spec = self._tools.get(name)
        if spec is None:
            self.audit.add(
                "tool.denied", identity.name, {"tool": name, "reason": "unknown"}
            )
            raise Denied("unknown tool")
        self.policy.check(identity, spec.action)
        if resource not in spec.resources:
            self.audit.add(
                "tool.denied", identity.name, {"tool": name, "reason": "resource_scope"}
            )
            raise Denied("resource outside tool scope")
        if not isinstance(payload, dict) or len(repr(payload)) > 10000:
            raise ValueError("invalid tool payload")
        result = spec.handler(payload)
        if len(repr(result)) > 20000:
            raise ValueError("tool result too large")
        self.audit.add(
            "tool.executed", identity.name, {"tool": name, "resource": resource}
        )
        return result
