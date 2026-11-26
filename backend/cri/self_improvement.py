"""Approval-gated self-improvement state machine; execution is delegated to sandbox provider."""
from dataclasses import dataclass, field
from enum import Enum
import uuid

class Stage(str, Enum):
    DISCOVERY="discovery"; PROPOSAL="proposal"; SECURITY="security"; SANDBOX="sandbox"; TEST="test"; COMPARE="compare"; APPROVE="approve"; PROMOTE="promote"; REJECTED="rejected"

@dataclass
class Improvement:
    id: str
    description: str
    stage: Stage = Stage.DISCOVERY
    evidence: dict = field(default_factory=dict)

class ImprovementWorkflow:
    ORDER = [Stage.DISCOVERY, Stage.PROPOSAL, Stage.SECURITY, Stage.SANDBOX, Stage.TEST, Stage.COMPARE, Stage.APPROVE, Stage.PROMOTE]
    def __init__(self, audit, tokens=None): self.audit, self.tokens, self.items = audit, tokens, {}
    def issue_human_approval(self, item_id: str):
        item = self.items[item_id]
        if item.stage != Stage.APPROVE or self.tokens is None:
            raise PermissionError("only an approval-stage item can receive a signed human token")
        return self.tokens.issue(item_id)
    def create(self, description: str):
        if not isinstance(description, str) or not description.strip() or len(description) > 1000: raise ValueError("invalid description")
        item = Improvement(uuid.uuid4().hex, description.strip()); self.items[item.id] = item
        self.audit.add("improvement.created", "system", {"id": item.id}); return item
    def advance(self, item_id: str, evidence: dict, approval_token: str | None = None):
        item = self.items[item_id]
        if item.stage in (Stage.PROMOTE, Stage.REJECTED): raise ValueError("terminal state")
        index = self.ORDER.index(item.stage)
        target = self.ORDER[index + 1]
        if target == Stage.PROMOTE:
            if self.tokens is None or not approval_token or not self.tokens.use(approval_token, item_id):
                raise PermissionError("valid one-time signed human approval required")
        if target == Stage.SECURITY and evidence.get("passed") is not True: raise PermissionError("security review must pass")
        if target == Stage.SANDBOX and evidence.get("sandbox_completed") is not True: raise PermissionError("sandbox evidence required")
        if target == Stage.COMPARE and evidence.get("tests_passed") is not True: raise PermissionError("tests must pass")
        item.stage = target; item.evidence[target.value] = dict(evidence)
        self.audit.add("improvement.stage", "workflow", {"id": item_id, "stage": target.value})
        return item
