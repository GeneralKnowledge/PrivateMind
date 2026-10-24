"""Independent safety checks: enforced by code below the models, never by the mind's text.

Every job passes `check` before it runs, whatever level asked for it. A higher level (a model,
now or later) can *propose* work only through `validate_proposal`, which forces its origin to
"model" so it cannot claim the operator's authority, and anything such a proposal would do to
the world waits for the operator's approval. Approvals are operator data in `approvals.jsonl`,
written by the CLI; the loop reads that file and never writes it. Each approval names one job and
one reason (`required_approval`), so it cannot be replayed for a later retry.

What this does and does not protect against: no model in an unattended path has file, shell or
network tools (`llm.call`), so no model can write `approvals.jsonl`, `tasks.jsonl`, `FLOOR.md` or
`state.json`. Anything that *can* write those files as the operator's user (another program, an
unconfined executor run with `--allow-unconfined`) is outside this layer's protection; the hash
pinned in state.json detects accidents, it is not a security boundary.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from . import capabilities, llm
from .capabilities import REGISTRY
from .events import now_iso
from .home import Home, append_jsonl, read_jsonl_tolerant, safe_id
from .mind import FloorTampered, Mind

DAILY_MODEL_BUDGET_USD = float(os.environ.get("PRIVATEBRAIN_DAILY_BUDGET_USD", "1.0"))
PROPOSABLE_FIELDS = {"prompt", "capability", "args", "domain", "replayable", "requires", "deadline",
                     "not_before", "every_s"}


@dataclass
class Verdict:
    allow: bool
    state: str = ""  # when not allowed: "blocked" (needs someone), "waiting" (needs time), "failed"
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


APPROVALS = "approvals.jsonl"


def required_approval(job) -> str:
    """The approval this job needs before it may run now, as a scope string, or "".

    An approval names one job *and* one reason. It does not carry over: approving a model's
    proposal does not approve a retry after a crash, and approving one retry does not approve
    the next one (the scope includes the attempt number)."""
    if job.interrupted and not job.replayable:
        return f"retry-after-interrupt-{job.attempts}"
    if not job.replayable and job.origin != "operator":
        return "run"
    cap = REGISTRY.get(job.capability) if job.capability else None
    if cap is not None and cap.side_effects != "none":
        return "run"
    return ""


def approvals(home: Home) -> set[tuple[str, str]]:
    """(job id, scope) pairs the operator has approved. Malformed lines are ignored, never
    read as an approval."""
    rows, _ = read_jsonl_tolerant(home.root / APPROVALS)
    return {(r["id"], r["scope"]) for r in rows
            if isinstance(r.get("id"), str) and isinstance(r.get("scope"), str) and r["scope"]}


def is_approved(job, approved: set[tuple[str, str]]) -> bool:
    need = required_approval(job)
    return not need or (job.id, need) in approved


def approve(home: Home, job, note: str = "") -> str:
    """Record the operator's approval for what `job` is blocked on now. Only the CLI calls this.
    Returns "approved" or "already approved"; raises ValueError if the job needs no approval."""
    need = required_approval(job)
    if not need or job.state != "blocked":
        raise ValueError(f"job {job.id} is {job.state} and is not waiting for an approval")
    if (job.id, need) in approvals(home):
        return "already approved"
    append_jsonl(home.root / APPROVALS, {"id": safe_id(job.id), "scope": need, "at": now_iso(), "note": note})
    return "approved"


def spent_today(home: Home) -> float:
    """Model spend today. A call that started and never finished (the process was killed)
    has no known cost, so it is charged at its cap: the budget errs towards stopping."""
    today = datetime.now(timezone.utc).date().isoformat()
    ledger = home.root / "llm_calls.jsonl"
    rows, _ = read_jsonl_tolerant(ledger)
    known = sum(float(r.get("cost_usd") or 0) for r in rows
                if r.get("status", "finished") != "started" and str(r.get("at", "")).startswith(today))
    unknown = sum(float(r.get("max_budget_usd") or 0) for r in llm.unfinished_calls(ledger)
                  if str(r.get("at", "")).startswith(today))
    return round(known + unknown, 6)


def check(job, *, home: Home, vitals: dict, approved: set[tuple[str, str]],
          budget_usd: float = DAILY_MODEL_BUDGET_USD) -> Verdict:
    """May this job run now? `job` is a substrate Job; `vitals` the latest sense reading.
    Called at dispatch, every time, whatever was checked when the job was created."""
    if not vitals.get("internal", {}).get("storage_writable", True):
        return Verdict(False, "waiting", "storage is not writable: results could not be kept",
                       ("storage",))
    if job.capability and job.capability in REGISTRY:
        try:
            capabilities.call_check(job.capability, job.args)
        except capabilities.CapabilityError as exc:
            return Verdict(False, "failed", f"bad arguments: {exc}")
    if not is_approved(job, approved):
        need = required_approval(job)
        if need.startswith("retry-after-interrupt"):
            why = ("interrupted during a run that acts on the world; check whether it happened, then "
                   f"`privatebrain approve {job.id}` to retry")
        elif job.capability and REGISTRY.get(job.capability) and REGISTRY[job.capability].side_effects != "none":
            why = f"{job.capability} has side effects ({REGISTRY[job.capability].side_effects}): needs approval"
        else:
            why = f"proposed by {job.origin} and acts on the world: needs `privatebrain approve {job.id}`"
        return Verdict(False, "blocked", why, ("approval",))
    if "remote_model" in job.needs and spent_today(home) >= budget_usd:
        return Verdict(False, "waiting", f"today's model budget of ${budget_usd} is spent", ("model_budget",))
    return ALLOW


def _iso_or_empty(v, name: str) -> str:
    if v in (None, ""):
        return ""
    if not isinstance(v, str):
        raise ValueError(f"{name} must be an ISO datetime string")
    try:
        datetime.fromisoformat(v)
    except ValueError as exc:
        raise ValueError(f"{name} {v!r} is not an ISO datetime") from exc
    return v


def validate_proposal(proposal: dict) -> dict:
    """Check a job proposed by a higher level. Returns the fields to enqueue, with origin set
    to "model" whatever the proposal says. Raises ValueError on anything malformed.

    A model cannot claim operator authority (origin is not a field it may set), cannot approve
    anything (approvals are not a job field), and its side-effecting work waits for approval."""
    if not isinstance(proposal, dict):
        raise ValueError("a proposal must be a JSON object")
    extra = set(proposal) - PROPOSABLE_FIELDS
    if extra:
        raise ValueError(f"fields a proposal may not set: {sorted(extra)}")
    out: dict = {}
    prompt = proposal.get("prompt", "")
    if not isinstance(prompt, str) or len(prompt) > 50_000:
        raise ValueError("prompt must be a string of at most 50,000 characters")
    out["prompt"] = prompt
    cap = proposal.get("capability", "")
    if not isinstance(cap, str):
        raise ValueError("capability must be a string")
    if cap and cap not in REGISTRY:
        raise ValueError(f"no capability named {cap!r}")
    if not cap and not prompt.strip():
        raise ValueError("a proposal needs a prompt or a capability")
    args = proposal.get("args", {})
    if not isinstance(args, dict):
        raise ValueError("args must be an object")
    if cap:
        try:
            capabilities.call_check(cap, args)
        except capabilities.CapabilityError as exc:
            raise ValueError(str(exc)) from exc
    out.update(capability=cap, args=args)
    domain = proposal.get("domain", "general")
    if not isinstance(domain, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,39}", domain):
        raise ValueError("domain must be a short lowercase slug")
    out["domain"] = domain
    replayable = proposal.get("replayable", True)
    if not isinstance(replayable, bool):
        raise ValueError("replayable must be true or false")
    out["replayable"] = replayable
    requires = proposal.get("requires", [])
    if not isinstance(requires, list) or len(requires) > 10 or not all(isinstance(r, str) and 0 < len(r) <= 60 for r in requires):
        raise ValueError("requires must be a list of at most 10 short need names")
    out["requires"] = requires
    out["deadline"] = _iso_or_empty(proposal.get("deadline"), "deadline")
    out["not_before"] = _iso_or_empty(proposal.get("not_before"), "not_before")
    every = proposal.get("every_s", 0) or 0
    if not isinstance(every, int) or isinstance(every, bool) or every < 0:
        raise ValueError("every_s must be a non-negative integer")
    if every and every < 60:
        raise ValueError("a recurring job may not run more often than once a minute")
    out["every_s"] = every
    return {**out, "origin": "model"}
