from typing import Any

from privatemind.worker.pairing_store import PairingStore
from privatemind.worker.trust import can_delegate


class WorkerScheduler:
    """Round-robin selection among workers with usable leases (M5)."""

    def __init__(self, pairing: PairingStore) -> None:
        self._pairing = pairing

    def select_worker(
        self,
        operation: str,
        *,
        contributor_id: str | None = None,
    ) -> dict[str, Any] | None:
        candidates = self._pairing.list_delegatable_workers(
            operation,
            contributor_id=contributor_id,
        )
        if not candidates:
            return None
        idx = self._pairing.next_schedule_index(len(candidates))
        return candidates[idx]
