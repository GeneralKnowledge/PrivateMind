"""October 2026 source-backed free-tier entitlement catalogue."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_ENTITLEMENTS_REL = Path("docs/data/free_tier_entitlements.json")


def entitlements_path() -> Path:
    return Path(__file__).resolve().parents[3] / _ENTITLEMENTS_REL


def load_entitlements(*, path: Path | None = None) -> dict[str, Any]:
    p = path or entitlements_path()
    with p.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if "entries" not in data or not isinstance(data["entries"], list):
        raise ValueError("entitlements file missing entries array")
    return data


def list_entries(
    data: dict[str, Any] | None = None,
    *,
    eligibility_class: str | None = None,
    provider_id: str | None = None,
    entry_kind: str | None = None,
) -> list[dict[str, Any]]:
    cat = data if data is not None else load_entitlements()
    out: list[dict[str, Any]] = []
    for row in cat.get("entries", []):
        if not isinstance(row, dict):
            continue
        if eligibility_class and row.get("eligibility_class") != eligibility_class:
            continue
        if provider_id and row.get("provider_id") != provider_id:
            continue
        if entry_kind and row.get("entry_kind") != entry_kind:
            continue
        out.append(row)
    return out


def category_a_provider_ids(data: dict[str, Any] | None = None) -> set[str]:
    return {str(r["provider_id"]) for r in list_entries(data, eligibility_class="A") if r.get("provider_id")}
