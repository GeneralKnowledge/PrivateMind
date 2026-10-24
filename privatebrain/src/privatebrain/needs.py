"""Needs: the brain's hunger for capability, asked for in batches and never taken."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from .home import Home

STATUSES = ("missing", "requested", "satisfied", "declined")
WEEKLY_REQUEST_BUDGET = 2


@dataclass
class Need:
    name: str
    why: str
    status: str = "missing"
    first_seen: str = ""
    requested_at: str = ""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "need"


class Needs:
    def __init__(self, home: Home):
        self.home = home

    def all(self) -> list[Need]:
        if not self.home.needs.is_file():
            return []
        return [Need(**n) for n in json.loads(self.home.needs.read_text(encoding="utf-8"))]

    def _save(self, needs: list[Need]) -> None:
        self.home.needs.write_text(
            json.dumps([asdict(n) for n in needs], indent=2) + "\n", encoding="utf-8"
        )

    def add(self, name: str, why: str) -> Need:
        """Record a need; a known one keeps its status (a satisfied need is not re-opened)."""
        needs = self.all()
        key = slug(name)
        for n in needs:
            if n.name == key:
                return n
        n = Need(name=key, why=why, first_seen=_now().isoformat(timespec="seconds"))
        needs.append(n)
        self._save(needs)
        return n

    def set_status(self, name: str, status: str) -> None:
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        needs = self.all()
        for n in needs:
            if n.name == slug(name):
                n.status = status
                self._save(needs)
                return
        raise KeyError(name)

    def unmet(self) -> list[Need]:
        return [n for n in self.all() if n.status == "missing"]

    def budget_left(self, state: dict, *, budget: int = WEEKLY_REQUEST_BUDGET) -> int:
        week_ago = _now() - timedelta(days=7)
        recent = [t for t in state.get("request_log", []) if datetime.fromisoformat(t) > week_ago]
        return max(0, budget - len(recent))

    def request_batch(self, state: dict) -> list[Need]:
        """Write ONE batched request for every missing need. Mutates `state` (request log)."""
        missing = self.unmet()
        if not missing:
            return []
        stamp = _now().isoformat(timespec="seconds")
        lines = [f"## Request — {stamp}", ""]
        lines += [f"- **{n.name}**: {n.why}" for n in missing]
        lines += [
            "",
            "Provision what you are willing to give, then run "
            "`privatebrain need set <name> satisfied` (or `declined`).",
            "",
        ]
        with self.home.requests.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        needs = self.all()
        for n in needs:
            if n.status == "missing":
                n.status = "requested"
                n.requested_at = stamp
        self._save(needs)
        state.setdefault("request_log", []).append(stamp)
        return missing


def needs_from_deliverable(text: str) -> list[tuple[str, str]]:
    """Lines under a `## Needs` heading, as (name, why). The mind asks for this format."""
    out: list[tuple[str, str]] = []
    m = re.search(r"^##\s*Needs\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    if not m:
        return out
    for line in m.group(1).splitlines():
        line = line.strip().lstrip("-*").strip()
        if not line:
            continue
        name, _, why = line.partition(":")
        out.append((name.strip(), (why or name).strip()))
    return out
