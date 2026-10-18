"""Donor/helper instruction index — agent-maintained playbooks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_PLAYBOOKS_REL = Path("docs/data/donor_helper_playbooks.json")


def helper_playbooks_path() -> Path:
    return Path(__file__).resolve().parents[3] / _PLAYBOOKS_REL


def load_helper_playbooks(*, path: Path | None = None) -> dict[str, Any]:
    p = path or helper_playbooks_path()
    with p.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if "playbooks" not in data:
        raise ValueError("donor helper playbooks file missing playbooks array")
    return data


def list_playbooks(data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    cat = data if data is not None else load_helper_playbooks()
    return [row for row in cat.get("playbooks", []) if isinstance(row, dict)]
