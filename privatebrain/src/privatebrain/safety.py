"""Independent safety checks: enforced by code below the models, never by the mind's text.

Every job passes `check` before it runs, whatever level asked for it. A higher level (a model,
now or later) can *propose* work only through `validate_proposal`, which forces its origin to
"model" so it cannot claim the operator's authority, and anything such a proposal would do to
the world waits for the operator's approval. Approvals are operator data in `approvals.jsonl`,
written by the CLI; the loop reads that file and never writes it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone

from .capabilities import REGISTRY
from .events import now_iso
from .home import Home, append_jsonl, read_jsonl
from .mind import FloorTampered, Mind

DAILY_MODEL_BUDGET_USD = float(os.environ.get("PRIVATEBRAIN_DAILY_BUDGET_USD", "1.0"))
PROPOSABLE_FIELDS = {"prompt", "capability", "args", "domain", "replayable", "requires", "deadline",
                     "not_before", "every_s"}


@dataclass
class Verdict:
    allow: bool
    state: str = ""  # when not allowed: "blocked" (needs someone) or "waiting" (needs time)
    reason: str = ""
    waiting_for: tuple[str, ...] = ()


ALLOW = Verdict(True)


def floor_problem(home: Home) -> str | None:
    try:
        Mind(home).floor_text()
    except FloorTampered as exc:
        return str(exc)
    except OSError as exc:
        return f"cannot read the floor: {exc}"
    return None


def approvals(home: Home) -> set[str]:
    return {r["id"] for r in read_jsonl(home.root / "approvals.jsonl")}


def approve(home: Home, job_id: str, note: str = "") -> None:
    append_jsonl(home.root / "approvals.jsonl", {"id": job_id, "at": now_iso(), "note": note})


def spent_today(home: Home) -> float:
    today = datetime.now(timezone.utc).date().isoformat()
    return round(sum(float(r.get("cost_usd") or 0) for r in read_jsonl(home.root / "llm_calls.jsonl")
                     if str(r.get("at", "")).startswith(today)), 6)


def check(job, *, home: Home, vitals: dict, approved: set[str],
          budget_usd: float = DAILY_MODEL_BUDGET_USD) -> Verdict:
    """May this job run now? `job` is a substrate Job; `vitals` the latest sense reading."""
    if not vitals.get("internal", {}).get("storage_writable", True):
        return Verdict(False, "waiting", "storage is not writable: results could not be kept",
                       ("storage",))
    ok = job.id in approved
    if not job.replayable and job.origin != "operator" and not ok:
        return Verdict(False, "blocked", f"proposed by {job.origin} and acts on the world: "
                       f"needs `privatebrain approve {job.id}`", ("approval",))
    if job.interrupted and not job.replayable and not ok:
        return Verdict(False, "blocked", "interrupted during a run that acts on the world; check whether "
                       f"it happened, then `privatebrain approve {job.id}` to retry", ("approval",))
    if job.capability and job.capability in REGISTRY:
        cap = REGISTRY[job.capability]
        if cap.side_effects != "none" and not ok:
            return Verdict(False, "blocked", f"{cap.name} has side effects ({cap.side_effects}): needs approval",
                           ("approval",))
    if "remote_model" in job.needs and spent_today(home) >= budget_usd:
        return Verdict(False, "waiting", f"today's model budget of ${budget_usd} is spent", ("model_budget",))
    return ALLOW


def validate_proposal(proposal: dict) -> dict:
    """Check a job proposed by a higher level. Returns the fields to enqueue, with origin set
    to "model" whatever the proposal says. Raises ValueError on anything malformed."""
    if not isinstance(proposal, dict):
        raise ValueError("a proposal must be a JSON object")
    extra = set(proposal) - PROPOSABLE_FIELDS
    if extra:
        raise ValueError(f"fields a proposal may not set: {sorted(extra)}")
    cap = proposal.get("capability", "")
    if cap and cap not in REGISTRY:
        raise ValueError(f"no capability named {cap!r}")
    if not cap and not str(proposal.get("prompt", "")).strip():
        raise ValueError("a proposal needs a prompt or a capability")
    if not isinstance(proposal.get("args", {}), dict):
        raise ValueError("args must be an object")
    if int(proposal.get("every_s", 0) or 0) and int(proposal["every_s"]) < 60:
        raise ValueError("a recurring job may not run more often than once a minute")
    return {**proposal, "origin": "model"}
