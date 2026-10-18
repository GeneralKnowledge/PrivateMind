"""Load free-tier provider catalog and compare with runtime quota state files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from privatemind.memory.store import MemoryStore
from privatemind.research.candidates import list_candidates, log_candidate

_CATALOG_REL = Path("docs/data/free_tier_provider_catalog.json")


def catalog_path() -> Path:
    # src/privatemind/research -> repo root
    return Path(__file__).resolve().parents[3] / _CATALOG_REL


def load_catalog(*, path: Path | None = None) -> dict[str, Any]:
    p = path or catalog_path()
    with p.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if "providers" not in data or not isinstance(data["providers"], dict):
        raise ValueError("catalog missing providers map")
    return data


def catalog_provider_ids(catalog: dict[str, Any] | None = None) -> set[str]:
    cat = catalog if catalog is not None else load_catalog()
    return set(cat["providers"].keys())


def load_quota_state(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    providers = data.get("providers")
    if not isinstance(providers, dict):
        raise ValueError("quota state missing providers map")
    return data


def diff_quota_state(
    quota: dict[str, Any],
    *,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cat = catalog if catalog is not None else load_catalog()
    catalog_ids = catalog_provider_ids(cat)
    file_ids = set(quota.get("providers", {}).keys())
    missing_in_catalog = sorted(file_ids - catalog_ids)
    missing_in_quota_file = sorted(catalog_ids - file_ids)
    return {
        "schema_version_quota": quota.get("schema_version"),
        "schema_version_catalog": cat.get("schema_version"),
        "in_quota_not_in_catalog": missing_in_catalog,
        "in_catalog_not_in_quota": missing_in_quota_file,
        "matched_count": len(file_ids & catalog_ids),
    }


def seed_candidates_from_catalog(
    memory: MemoryStore,
    *,
    catalog: dict[str, Any] | None = None,
    skip_existing: bool = True,
) -> dict[str, Any]:
    cat = catalog if catalog is not None else load_catalog()
    existing = {r.get("slug") for r in list_candidates(memory)} if skip_existing else set()
    seeded: list[str] = []
    skipped: list[str] = []
    for provider_id, meta in sorted(cat["providers"].items()):
        if not isinstance(meta, dict):
            continue
        slug = str(meta.get("candidate_slug") or provider_id.replace("_", "-"))
        if skip_existing and slug in existing:
            skipped.append(slug)
            continue
        log_candidate(
            memory,
            slug=slug,
            name=str(meta.get("name") or provider_id),
            category=str(meta.get("category") or "llm"),
            docs_url=str(meta.get("docs_url") or ""),
            notes=str(meta.get("notes") or ""),
            verdict="pending",
            probe_result={"provider_id": provider_id, "base_url": meta.get("base_url")},
        )
        seeded.append(slug)
    return {"seeded": seeded, "skipped": skipped}
