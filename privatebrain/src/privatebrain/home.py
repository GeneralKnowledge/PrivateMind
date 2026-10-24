"""A brain home: every path and the small persistent state, in one place."""

from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

DEFAULT_HOME = Path(os.environ.get("PRIVATEBRAIN_HOME", "~/.privatebrain")).expanduser()

DEFAULT_STATE = {
    "floor_sha": "",
    "mind_version": 0,
    "auto_adopt": True,
    "activities": [],
    "improved_at": {},
    "pending_adoptions": [],
    "request_log": [],
}


@dataclass(frozen=True)
class Home:
    root: Path

    @property
    def floor(self) -> Path:
        return self.root / "FLOOR.md"

    @property
    def state_file(self) -> Path:
        return self.root / "state.json"

    @property
    def mind_current(self) -> Path:
        return self.root / "mind" / "current"

    @property
    def mind_versions(self) -> Path:
        return self.root / "mind" / "versions"

    @property
    def tasks(self) -> Path:
        return self.root / "tasks.jsonl"

    @property
    def journal(self) -> Path:
        return self.root / "journal.jsonl"

    @property
    def episodes(self) -> Path:
        return self.root / "episodes"

    @property
    def needs(self) -> Path:
        return self.root / "needs.json"

    @property
    def requests(self) -> Path:
        return self.root / "REQUESTS.md"

    @property
    def reflections(self) -> Path:
        return self.root / "REFLECTIONS.md"

    @property
    def library(self) -> Path:
        return self.root / "library"

    @property
    def runs(self) -> Path:
        return self.root / "runs"

    def exists(self) -> bool:
        return self.state_file.is_file()

    def load_state(self) -> dict:
        if not self.state_file.is_file():
            return json.loads(json.dumps(DEFAULT_STATE))
        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        return {**json.loads(json.dumps(DEFAULT_STATE)), **state}

    def save_state(self, state: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.state_file)


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    os.replace(tmp, path)


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


@contextmanager
def locked(path: Path):
    """An exclusive advisory lock beside `path`, so the CLI and a running loop do not
    lose each other's writes to the same queue."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_name(path.name + ".lock"), "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def write_json(path: Path, obj) -> None:
    """Write-then-rename, so a crash leaves the old file or the new one, never half of one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)
