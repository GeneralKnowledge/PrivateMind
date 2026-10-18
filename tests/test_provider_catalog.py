import json
from pathlib import Path

from privatemind.db import Database
from privatemind.memory.store import MemoryStore
from privatemind.research.provider_catalog import (
    catalog_provider_ids,
    diff_quota_state,
    load_catalog,
    seed_candidates_from_catalog,
)

USER_PROVIDER_KEYS = {
    "aion_labs",
    "cohere",
    "google_gemini",
    "mistral",
    "z_ai",
    "cloudflare_workers_ai",
    "groq",
    "huggingface",
    "kilo",
    "llm7",
    "modelscope",
    "nvidia_nim",
    "ollama_cloud",
    "openrouter",
    "ovhcloud_ai_endpoints",
    "siliconflow",
}


def test_catalog_covers_user_quota_provider_keys() -> None:
    assert USER_PROVIDER_KEYS <= catalog_provider_ids(load_catalog())


def test_diff_quota_state_empty_gaps_when_full_file(tmp_path: Path) -> None:
    quota = {
        "schema_version": "2026-09-27",
        "providers": {k: {"enabled": True} for k in USER_PROVIDER_KEYS},
    }
    path = tmp_path / "state.json"
    path.write_text(json.dumps(quota), encoding="utf-8")
    diff = diff_quota_state(json.loads(path.read_text()))
    assert diff["in_quota_not_in_catalog"] == []
    assert diff["matched_count"] == len(USER_PROVIDER_KEYS)


def test_seed_catalog_skips_existing_slug(tmp_path) -> None:
    db = Database(tmp_path / "r.sqlite3")
    db.initialize()
    mem = MemoryStore(db)
    first = seed_candidates_from_catalog(mem)
    assert len(first["seeded"]) >= 10
    second = seed_candidates_from_catalog(mem)
    assert second["seeded"] == []
    assert len(second["skipped"]) == len(first["seeded"])
