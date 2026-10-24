"""The task queue and the journal of finished episodes."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from .home import Home, append_jsonl, locked, read_jsonl, write_jsonl


@dataclass
class Task:
    id: str
    prompt: str
    domain: str = "general"
    replayable: bool = True
    # Read by the substrate loop (`substrate.py`); the v0 tick ignores them.
    capability: str = ""  # a registry capability to call with `args` instead of a prompt
    args: dict = field(default_factory=dict)
    requires: list = field(default_factory=list)  # need names that must be satisfied first
    deadline: str = ""  # ISO datetime
    not_before: str = ""  # ISO datetime
    every_s: int = 0  # re-run this often once done
    origin: str = "operator"  # operator | schedule | model


@dataclass
class Episode:
    id: str
    prompt: str
    domain: str
    replayable: bool
    mind_version: int
    ok: bool
    error: str = ""
    created: str = ""


def new_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{stamp}-{uuid.uuid4().hex[:6]}"


class Journal:
    def __init__(self, home: Home):
        self.home = home

    def enqueue(self, prompt: str, *, domain: str = "general", replayable: bool = True, **extra) -> Task:
        t = Task(id=new_id(), prompt=prompt, domain=domain, replayable=replayable, **extra)
        with locked(self.home.tasks):
            append_jsonl(self.home.tasks, asdict(t))
        return t

    def queued(self) -> list[Task]:
        return [Task(**r) for r in read_jsonl(self.home.tasks)]

    def pop(self) -> Task | None:
        with locked(self.home.tasks):
            rows = read_jsonl(self.home.tasks)
            if not rows:
                return None
            write_jsonl(self.home.tasks, rows[1:])
        return Task(**rows[0])

    def record(self, ep: Episode) -> None:
        ep.created = ep.created or datetime.now(timezone.utc).isoformat(timespec="seconds")
        append_jsonl(self.home.journal, asdict(ep))

    def episodes(self) -> list[Episode]:
        return [Episode(**r) for r in read_jsonl(self.home.journal)]

    def get(self, episode_id: str) -> Episode:
        for ep in self.episodes():
            if ep.id == episode_id:
                return ep
        raise KeyError(episode_id)

    def replayable(self, domain: str) -> list[Episode]:
        return [e for e in self.episodes() if e.domain == domain and e.replayable and e.ok]
