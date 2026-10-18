import json
from datetime import datetime, timezone
from typing import Any


def _parse_utc(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def lease_limits(lease: dict[str, Any]) -> dict[str, Any]:
    raw = lease.get("limits_json") or "{}"
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw)


def lease_expired(lease: dict[str, Any], *, now: datetime | None = None) -> bool:
    expires_at = lease.get("expires_at")
    if not expires_at:
        return False
    current = now or datetime.now(timezone.utc)
    return _parse_utc(str(expires_at)) <= current


def lease_jobs_remaining(lease: dict[str, Any]) -> int | None:
    limits = lease_limits(lease)
    max_jobs = limits.get("max_jobs")
    if max_jobs is None:
        return None
    used = int(lease.get("jobs_used") or 0)
    return max(0, int(max_jobs) - used)


def lease_usable(lease: dict[str, Any], operation: str, *, now: datetime | None = None) -> bool:
    if int(lease.get("revoked") or 0):
        return False
    ops = json.loads(lease["operations_json"])
    if operation not in ops:
        return False
    if lease_expired(lease, now=now):
        return False
    remaining = lease_jobs_remaining(lease)
    if remaining is not None and remaining <= 0:
        return False
    return True
