from datetime import datetime, timezone
from typing import Any

from privatemind.worker.lease_util import lease_expired, lease_jobs_remaining, lease_limits
from privatemind.worker.pairing_store import PairingStore
from privatemind.worker.trust import can_delegate


def worker_network_report(pairing: PairingStore) -> dict[str, Any]:
    workers = pairing.list_workers()
    leases = pairing.list_leases()
    now = datetime.now(timezone.utc)
    summary = {
        "workers_total": len(workers),
        "delegatable": 0,
        "quarantined": 0,
        "restricted": 0,
        "revoked": 0,
        "leases_active": 0,
        "leases_exhausted": 0,
        "leases_expired": 0,
    }
    worker_rows: list[dict[str, Any]] = []
    for w in workers:
        state = str(w.get("trust_state") or "")
        if state == "quarantined":
            summary["quarantined"] += 1
        elif state == "restricted":
            summary["restricted"] += 1
        elif state == "revoked":
            summary["revoked"] += 1
        if can_delegate(state):
            summary["delegatable"] += 1
        rep = pairing.worker_reputation(w["fingerprint"])
        worker_rows.append(
            {
                "fingerprint": w["fingerprint"],
                "label": w.get("label"),
                "trust_state": state,
                "contributor_id": w.get("contributor_id"),
                "consecutive_failures": w.get("consecutive_failures"),
                "reputation": rep,
            }
        )

    for lease in leases:
        if int(lease.get("revoked") or 0):
            continue
        if lease_expired(lease, now=now):
            summary["leases_expired"] += 1
            continue
        remaining = lease_jobs_remaining(lease)
        if remaining is not None and remaining <= 0:
            summary["leases_exhausted"] += 1
            continue
        summary["leases_active"] += 1

    return {"summary": summary, "workers": worker_rows}


def merge_setup_report(readiness: dict[str, Any], worker_report: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(readiness)
    if worker_report is not None:
        out["worker_network"] = worker_report
    return out
