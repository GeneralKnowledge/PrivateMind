"""Donor resource catalog — commitment levels, kinds, storage backends."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CATALOG_REL = Path("docs/data/donor_resource_catalog.json")


def donor_catalog_path() -> Path:
    return Path(__file__).resolve().parents[3] / _CATALOG_REL


def load_donor_resource_catalog(*, path: Path | None = None) -> dict[str, Any]:
    p = path or donor_catalog_path()
    with p.open(encoding="utf-8") as fh:
        data = json.load(fh)
    for key in ("commitment_levels", "resource_kinds", "storage_backends"):
        if key not in data:
            raise ValueError(f"donor resource catalog missing {key}")
    return data


def valid_commitment_level_ids(catalog: dict[str, Any] | None = None) -> set[str]:
    cat = catalog if catalog is not None else load_donor_resource_catalog()
    return {row["id"] for row in cat.get("commitment_levels", []) if isinstance(row, dict) and row.get("id")}


def valid_resource_kind_ids(catalog: dict[str, Any] | None = None) -> set[str]:
    cat = catalog if catalog is not None else load_donor_resource_catalog()
    return {row["id"] for row in cat.get("resource_kinds", []) if isinstance(row, dict) and row.get("id")}


def valid_storage_backend_ids(catalog: dict[str, Any] | None = None) -> set[str]:
    cat = catalog if catalog is not None else load_donor_resource_catalog()
    return {row["id"] for row in cat.get("storage_backends", []) if isinstance(row, dict) and row.get("id")}
