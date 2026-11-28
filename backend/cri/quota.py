"""Data-driven request quota enforcement; storage is injected for testability."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .db.models import PlanRecord, UsageRecord, FeatureFlagRecord, UserAccountRecord

@dataclass(frozen=True)
class QuotaDecision:
    allowed: bool
    reason: str
    used: int = 0
    limit: int | None = None

class QuotaService:
    def __init__(self, sessions, audit, enabled: bool = True, owner_bypass: bool = True):
        self.sessions, self.audit, self.enabled, self.owner_bypass = sessions, audit, enabled, owner_bypass

    def check(self, user_id: str, feature: str, *, is_owner: bool = False) -> QuotaDecision:
        if not self.enabled:
            decision = QuotaDecision(True, "quota_disabled")
        elif is_owner and self.owner_bypass:
            decision = QuotaDecision(True, "owner_bypass")
        else:
            with self.sessions() as db:
                user = db.get(UserAccountRecord, user_id)
                plan = db.get(PlanRecord, user.plan_id) if user else None
                if user is None or not user.active:
                    decision = QuotaDecision(False, "unknown_or_inactive_user")
                elif plan is None:
                    decision = QuotaDecision(False, "plan_not_found")
                else:
                    flag = db.get(FeatureFlagRecord, feature)
                    if flag is not None and not flag.enabled:
                        decision = QuotaDecision(False, "feature_disabled")
                    else:
                        limit = plan.quotas.get(feature)
                        used = db.scalar(select(func.coalesce(func.sum(UsageRecord.quantity), 0)).where(
                            UsageRecord.user_id == user_id, UsageRecord.feature == feature,
                            UsageRecord.usage_date == date.today())) or 0
                        decision = QuotaDecision(limit is None or used < int(limit), "unlimited" if limit is None else ("within_quota" if used < int(limit) else "quota_exceeded"), int(used), None if limit is None else int(limit))
        if self.audit:
            self.audit.add("quota.decision", user_id, {"feature": feature, "allowed": decision.allowed, "reason": decision.reason, "used": decision.used, "limit": decision.limit})
        return decision

    def record(self, user_id: str, feature: str, quantity: int = 1) -> None:
        if quantity < 1: raise ValueError("quantity must be positive")
        with self.sessions() as db:
            db.add(UsageRecord(user_id=user_id, feature=feature, quantity=quantity, usage_date=date.today()))
            db.commit()
