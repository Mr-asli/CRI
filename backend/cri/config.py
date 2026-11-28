"""Fail-closed environment validation for security-critical deployment settings."""
from __future__ import annotations
import os

REQUIRED_SECRETS = ("CRI_ADMIN_TOKEN", "CRI_APPROVAL_SECRET")

def validate_environment(env=None):
    values = os.environ if env is None else env
    missing = [key for key in REQUIRED_SECRETS if len(values.get(key, "").encode()) < 32]
    if missing:
        raise RuntimeError("required security configuration missing or too short: " + ", ".join(missing))
    for key in ("QUOTA_ENABLED", "OWNER_BYPASS_QUOTA", "LLM_ENABLED"):
        if key in values and values[key].lower() not in {"true", "false", "1", "0", "yes", "no"}:
            raise RuntimeError(f"{key} must be a boolean")
    for key in ("ALERT_CPU_PERCENT", "ALERT_MEMORY_PERCENT", "ALERT_DISK_PERCENT"):
        if key in values:
            try: value = float(values[key])
            except ValueError as exc: raise RuntimeError(f"{key} must be numeric") from exc
            if not 0 < value <= 100: raise RuntimeError(f"{key} must be between 0 and 100")
    return True

def env_bool(name, default=False):
    value = os.getenv(name)
    return default if value is None else value.lower() in {"true", "1", "yes"}
