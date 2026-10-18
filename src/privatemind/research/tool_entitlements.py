"""Web search and other non-LLM tool entitlements catalogue."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_TOOLS_REL = Path("docs/data/free_tier_tool_entitlements.json")


def tool_entitlements_path() -> Path:
    return Path(__file__).resolve().parents[3] / _TOOLS_REL


def load_tool_entitlements(*, path: Path | None = None) -> dict[str, Any]:
    p = path or tool_entitlements_path()
    with p.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if "entries" not in data or not isinstance(data["entries"], list):
        raise ValueError("tool entitlements missing entries array")
    return data


def list_tool_entries(
    data: dict[str, Any] | None = None,
    *,
    eligibility_class: str | None = None,
    tool_kind: str | None = None,
    provider_id: str | None = None,
) -> list[dict[str, Any]]:
    cat = data if data is not None else load_tool_entitlements()
    out: list[dict[str, Any]] = []
    for row in cat.get("entries", []):
        if not isinstance(row, dict):
            continue
        if eligibility_class and row.get("eligibility_class") != eligibility_class:
            continue
        if tool_kind and row.get("tool_kind") != tool_kind:
            continue
        if provider_id and row.get("provider_id") != provider_id:
            continue
        out.append(row)
    return out
