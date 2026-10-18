"""Worker trust states (M4 adversarial verification)."""

from enum import Enum


class WorkerTrustState(str, Enum):
    PAIRED = "paired"
    RESTRICTED = "restricted"
    QUARANTINED = "quarantined"
    REVOKED = "revoked"


def can_delegate(state: str | None) -> bool:
    return state in (WorkerTrustState.PAIRED.value, WorkerTrustState.RESTRICTED.value)


def auto_accept_results(state: str | None) -> bool:
    return state == WorkerTrustState.PAIRED.value
