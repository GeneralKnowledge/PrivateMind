"""Structured events: what the senses and the loop noticed, as data rather than prose.

An event is a flat JSON object with a `type`, a `timestamp`, a `severity` and the `source`
that raised it, plus whatever fields describe it. `events.jsonl` is append-only: ordinary
code reacts to events as they are raised, and a model (later) may read them to explain them.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .home import Home, append_jsonl, locked, read_jsonl

SEVERITIES = ("info", "warning", "critical")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def event(type: str, *, source: str, severity: str = "info", **fields) -> dict:
    if severity not in SEVERITIES:
        raise ValueError(f"severity must be one of {SEVERITIES}")
    return {"type": type, "timestamp": now_iso(), "severity": severity, "source": source, **fields}


class EventLog:
    def __init__(self, home: Home):
        self.path: Path = home.root / "events.jsonl"

    def emit(self, ev: dict) -> dict:
        with locked(self.path):
            append_jsonl(self.path, ev)
        return ev

    def tail(self, n: int = 50, *, type: str | None = None) -> list[dict]:
        rows = read_jsonl(self.path)
        if type:
            rows = [r for r in rows if r.get("type") == type]
        return rows[-n:]
