from cri.core import Denied, Identity, Policy
from .base import (
    MasterAgent,
    DeveloperAgent,
    ResearchAgent,
    TestingAgent,
    SecurityAuditorAgent,
    MemoryAgent,
)

AGENT_TYPES = {
    c.role: c
    for c in (
        MasterAgent,
        DeveloperAgent,
        ResearchAgent,
        TestingAgent,
        SecurityAuditorAgent,
        MemoryAgent,
    )
}


class AgentFactory:
    def __init__(self, policy: Policy, gateway):
        self.policy, self.gateway = policy, gateway

    def create(self, parent: Identity, name: str, role: str):
        if role not in AGENT_TYPES:
            raise Denied("unknown agent role")
        child = self.policy.child(parent, name, role)
        return AGENT_TYPES[role](child, self.gateway)

    def create_root(self, name: str, role: str):
        if role not in AGENT_TYPES:
            raise Denied("unknown agent role")
        identity = self.policy.identity(name, role)
        return AGENT_TYPES[role](identity, self.gateway)
