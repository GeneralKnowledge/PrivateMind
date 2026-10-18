"""Portal configuration — repo skeleton + optional data-dir override."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CONFIG_REL = Path("docs/data/portal_config.json")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_config_path() -> Path:
    return repo_root() / _CONFIG_REL


def load_portal_config(*, path: Path | None = None) -> dict[str, Any]:
    p = path or default_config_path()
    with p.open(encoding="utf-8") as fh:
        return json.load(fh)


def instruction_path(config: dict[str, Any], role: str) -> Path:
    paths = config.get("instruction_paths") or {}
    rel = paths.get(role)
    if not rel:
        raise KeyError(f"unknown instruction role: {role}")
    return repo_root() / rel
