"""Lessons: what experiments observed, kept with their evidence, scope and limits.

A lesson is a claim about a kind of mind change ("asking for X fixed check Y"), never a rule the
brain must follow. `lessons.jsonl` is append-only: a later experiment adds a row, it never edits
one, so negative or contradicting evidence sits beside the positive evidence instead of
replacing it. What a claim currently amounts to is computed from all its rows (`summarize`).

Status words are deliberately modest, because the suite is small:

- `observed`: train scores rose on the tasks the optimizer saw. Nothing more.
- `held-out (in-suite)`: also rose on the suite's held-out tasks, which the optimizer never
  saw. Evidence of transfer *within this suite*, not general improvement.
- `not supported`: the change was evaluated and did not beat noise, or regressed.
- `unsafe`: the change failed a safety task.
- `contested`: rows for the same checks disagree.

An optimizer may read relevant lessons (`relevant`) to shape a hypothesis or a candidate. A
lesson never changes the gate: every candidate is still evaluated and decided on its scores.
"""

from __future__ import annotations

from .home import Home, append_jsonl, read_jsonl_tolerant

LIMITATIONS = (
    "measured on a 9-task suite (4 train, 3 held-out, 2 safety) with a few repeats per task",
    "tasks are single-turn and run with no tools",
    "held-out tasks are in the same suite and style as train tasks: transfer beyond the suite is untested",
)


def path(home: Home):
    return home.root / "lessons.jsonl"


def _status(st: dict) -> str:
    c = st.get("checks") or {}
    if st["decision"] in ("adopted", "pending-approval"):
        if (c.get("heldout") or {}).get("delta", 0) > (st.get("rule") or {}).get("heldout_tolerance", 0.05):
            return "held-out (in-suite)"
        return "observed"
    if not (c.get("safety") or {}).get("passed", True):
        return "unsafe"
    return "not supported"


def from_experiment(st: dict) -> dict | None:
    """The lesson row an evaluated mind-change experiment leaves, adopted or not. Experiments
    that never evaluated a candidate (no weakness, no candidate, invalid) teach nothing here."""
    if st.get("kind") != "mind-change" or not st.get("checks") or not st.get("problem"):
        return None
    c = st["checks"]
    cand = st.get("candidate") or {}
    addresses = [w["check"] for w in st["problem"]["failing_checks"]]
    status = _status(st)
    verb = "raised" if status in ("observed", "held-out (in-suite)") else "did not reliably raise"
    return {
        "id": f"lesson-{st['id']}",
        "kind": "positive" if status in ("observed", "held-out (in-suite)") else "negative",
        "claim": (f"{cand.get('rationale', 'a mind change')} {verb} the score on "
                  f"{', '.join(addresses[:4])} (train {c['train']['baseline']} -> {c['train']['candidate']})"),
        "addresses": addresses,
        "components": cand.get("components", []),
        "status": status,
        "scope": {"supported_on": [t.split("@")[0] for t in st["tasks"]["train"] + st["tasks"]["heldout"]],
                  "untested": "anything outside this suite; tool-using and multi-turn tasks"},
        "limitations": list(LIMITATIONS),
        "evidence": [{"experiment": st["id"], "decision": st["decision"], "train_gain": c["train"]["gain"],
                      "stderr": c["train"]["stderr"], "heldout_delta": c["heldout"]["delta"],
                      "safety": c["safety"]["passed"], "reasons": st.get("reasons", [])}],
        "origin_experiment": st["id"],
        "informed_by": st.get("prior_lessons", []),
        "mind_version": st.get("adopted_version"),
    }


def record(home: Home, st: dict) -> dict | None:
    row = from_experiment(st)
    if row:
        append_jsonl(path(home), row)
    return row


def all_rows(home: Home) -> list[dict]:
    rows, _ = read_jsonl_tolerant(path(home))
    return rows


def relevant(home: Home, failing_checks: list[str], *, limit: int = 5) -> list[dict]:
    """Lessons about any of these checks, newest first, each with every row's evidence."""
    want = set(failing_checks)
    hits = [r for r in all_rows(home) if want & set(r.get("addresses", []))]
    return list(reversed(hits))[:limit]


def summarize(rows: list[dict]) -> dict:
    """What the evidence on a set of checks amounts to, contradictions included."""
    kinds = {r.get("kind") for r in rows}
    return {
        "lessons": [r.get("id") for r in rows],
        "status": "contested" if {"positive", "negative"} <= kinds else (rows[0].get("status") if rows else "none"),
        "positive": sum(r.get("kind") == "positive" for r in rows),
        "negative": sum(r.get("kind") == "negative" for r in rows),
    }


def render_for_optimizer(rows: list[dict]) -> str:
    """Prior lessons as text an optimizer can read: evidence and limits, not instructions."""
    if not rows:
        return ""
    lines = ["Earlier experiments on these checks (recorded evidence, not rules; the new candidate "
             "is judged only on its own scores):"]
    for r in rows:
        ev = r.get("evidence", [{}])[0]
        lines.append(f"- [{r.get('status')}] {r.get('claim')} (experiment {ev.get('experiment')}: "
                     f"train gain {ev.get('train_gain')}, held-out delta {ev.get('heldout_delta')}, "
                     f"safety {'passed' if ev.get('safety') else 'FAILED'})")
    return "\n".join(lines)
