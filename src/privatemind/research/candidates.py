import json
from typing import Any

from privatemind.memory.store import MemoryStore
from privatemind.trust import Provenance, TrustLevel

KIND = "free_tier_candidate"


def log_candidate(
    memory: MemoryStore,
    *,
    slug: str,
    name: str,
    category: str,
    docs_url: str = "",
    notes: str = "",
    verdict: str = "pending",
    probe_result: dict[str, Any] | None = None,
) -> None:
    payload = {
        "name": name,
        "category": category,
        "docs_url": docs_url,
        "notes": notes,
        "verdict": verdict,
        "probe": probe_result,
    }
    memory.upsert(
        kind=KIND,
        key=slug,
        content=json.dumps(payload),
        provenance=Provenance.TOOL_OUTPUT,
        trust_level=TrustLevel.UNVERIFIED,
        metadata={"category": category, "verdict": verdict},
    )


def list_candidates(memory: MemoryStore, *, verdict: str | None = None) -> list[dict[str, Any]]:
    rows = memory.search(kind=KIND, limit=200)
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row.get("content") or "{}")
        except json.JSONDecodeError:
            payload = {}
        if verdict and payload.get("verdict") != verdict:
            continue
        out.append({"slug": row.get("key"), **payload})
    return sorted(out, key=lambda r: str(r.get("slug") or ""))
