import json
from typing import Any

from privatemind.memory.store import MemoryStore
from privatemind.trust import Provenance, TrustLevel


class ImprovementTracker:
    """Persistent limitation and proposal records (trusted-core writes)."""

    def __init__(self, memory: MemoryStore) -> None:
        self._memory = memory

    def record_limitation(
        self,
        *,
        key: str,
        summary: str,
        evidence: str,
        severity: str = "medium",
        component: str = "unknown",
        status: str = "open",
    ) -> None:
        payload = {
            "summary": summary,
            "evidence": evidence,
            "severity": severity,
            "component": component,
            "status": status,
        }
        self._memory.upsert(
            kind="limitation",
            key=key,
            content=json.dumps(payload),
            provenance=Provenance.TRUSTED_CORE,
            trust_level=TrustLevel.VERIFIED,
            metadata={"severity": severity, "component": component},
        )

    def record_outcome(
        self,
        *,
        key: str,
        limitation_key: str,
        success: bool,
        notes: str,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "limitation_key": limitation_key,
            "success": success,
            "notes": notes,
            "metrics": metrics or {},
        }
        self._memory.upsert(
            kind="improvement_outcome",
            key=key,
            content=json.dumps(payload),
            provenance=Provenance.TRUSTED_CORE,
            trust_level=TrustLevel.VERIFIED,
        )
