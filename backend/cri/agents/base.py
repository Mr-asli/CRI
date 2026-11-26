from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from cri.core import Identity

@dataclass
class AgentResult:
    agent: str
    task_id: str
    status: str
    output: dict[str, Any]

class Agent(ABC):
    role = "base"
    def __init__(self, identity: Identity, gateway):
        if identity.role != self.role:
            raise ValueError("identity role mismatch")
        self.identity, self.gateway = identity, gateway
        self.history: list[AgentResult] = []

    def execute(self, task_id: str, payload: dict[str, Any]) -> AgentResult:
        result = AgentResult(self.role, task_id, "completed", self.run(payload))
        self.history.append(result)
        return result

    @abstractmethod
    def run(self, payload: dict[str, Any]) -> dict[str, Any]: ...

class MasterAgent(Agent):
    role = "master"
    def run(self, payload):
        goal = str(payload.get("goal", "")).strip()
        if len(goal) < 3: raise ValueError("goal too short")
        return {"goal": goal, "plan": ["research", "develop", "test", "security_review"], "requires_human_approval": True}

class DeveloperAgent(Agent):
    role = "developer"
    def run(self, payload):
        return {"proposal": str(payload.get("specification", ""))[:4000], "status": "draft", "promotion": "forbidden_without_human_approval"}

class ResearchAgent(Agent):
    role = "research"
    def run(self, payload):
        question = str(payload.get("question", "")).strip()
        if not question: raise ValueError("question required")
        return {"question": question, "findings": [], "source_status": "no_external_sources_configured"}

class TestingAgent(Agent):
    role = "testing"
    def run(self, payload):
        return {"test_plan": list(payload.get("checks", [])), "execution": "not_run_without_sandbox", "fail_closed": True}

class SecurityAuditorAgent(Agent):
    role = "auditor"
    def run(self, payload):
        violations = list(payload.get("invariants_violated", []))
        return {"passed": not violations, "violations": violations, "decision": "pass" if not violations else "reject"}

class MemoryAgent(Agent):
    role = "memory"
    def run(self, payload):
        text = str(payload.get("text", ""))
        record = self.gateway.invoke(self.identity, "memory.write", "memory", {"text": text})
        return {"stored": record}
