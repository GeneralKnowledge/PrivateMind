"""Orchestrate free-tier discovery: GitHub lists, hub collections, gap analysis."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from privatemind.research.entitlements import category_a_provider_ids, load_entitlements
from privatemind.research.github_lists import (
    RETIRED_PROVIDER_IDS,
    provider_ids_in_text,
    sync_github_sources,
)
from privatemind.research.provider_catalog import catalog_provider_ids, load_catalog

_DISCOVERY_SOURCES_REL = Path("docs/data/free_tier_discovery_sources.json")
_LATEST_REPORT_REL = Path("docs/data/free_tier_discovery_latest.json")

# provider_id → probe hint when github-sync finds a gap
_GAP_PROBE_HINTS: dict[str, str] = {
    "cerebras": "https://inference.cerebras.ai/ — Oct 2026: trial often card-gated; verify before A.",
    "fireworks_ai": "https://fireworks.ai/ — trial credits, not permanent free.",
    "vercel_ai_gateway": "https://vercel.com/ai — gateway free slice; verify model list.",
    "scaleway_genai": "https://www.scaleway.com/en/generative-apis/ — EU; check always-free vs trial.",
    "deepseek_api": "https://platform.deepseek.com/ — verify standing free vs promo.",
    "ai_horde": "https://aihorde.net/ — volunteer queue; anon key 0000000000; not OpenAI SLA.",
    "typhoon": "https://opentyphoon.ai/ — OpenAI-compat; Thai-focused; beta showcase.",
    "orcarouter": "https://orcarouter.com/ — aggregator; verify :free routes.",
    "opencode_zen": "https://opencode.ai/zen — time-limited -free suffix models.",
}


def discovery_sources_path() -> Path:
    return Path(__file__).resolve().parents[3] / _DISCOVERY_SOURCES_REL


def latest_report_path() -> Path:
    return Path(__file__).resolve().parents[3] / _LATEST_REPORT_REL


def load_discovery_sources(*, path: Path | None = None) -> dict[str, Any]:
    p = path or discovery_sources_path()
    with p.open(encoding="utf-8") as fh:
        return json.load(fh)


def fetch_url_text(url: str, *, timeout_seconds: float = 25.0) -> str:
    resp = httpx.get(url, timeout=timeout_seconds, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


def provider_names_in_markdown_tables(text: str) -> list[str]:
    """Rough extract of bold provider names from markdown tables (**Name**)."""
    names: list[str] = []
    for m in re.finditer(r"\*\*([^*]+)\*\*", text):
        name = m.group(1).strip()
        if len(name) < 3 or len(name) > 80:
            continue
        if name.lower().startswith("provider"):
            continue
        names.append(name)
    return names


def run_discovery(*, github_source_id: str | None = None, fetch_github: bool = True) -> dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    entitlements = load_entitlements()
    catalog = load_catalog()
    catalog_ids = catalog_provider_ids(catalog)
    entitlement_ids = {str(e.get("provider_id")) for e in entitlements.get("entries", []) if e.get("provider_id")}
    category_a = sorted(category_a_provider_ids(entitlements))

    github = sync_github_sources(source_id=github_source_id, fetch=fetch_github, catalog=catalog)
    gaps = list(github.get("in_github_lists_not_in_catalog") or [])
    gap_details = [
        {
            "provider_id": pid,
            "in_entitlements": pid in entitlement_ids,
            "suggested_class": "C",
            "probe_hint": _GAP_PROBE_HINTS.get(pid, "Add official docs URL after probe."),
        }
        for pid in gaps
    ]

    hub_mentions: dict[str, Any] = {}
    errors: dict[str, str] = {}
    meta = load_discovery_sources()
    for coll in meta.get("github_collections", []):
        if not isinstance(coll, dict):
            continue
        cid = str(coll.get("id") or "")
        url = str(coll.get("raw_url") or "")
        if not url:
            continue
        try:
            body = fetch_url_text(url)
        except httpx.HTTPError as exc:
            errors[cid] = str(exc)
            continue
        ids = provider_ids_in_text(body)
        hub_mentions[cid] = {
            "url": url,
            "provider_ids_from_aliases": sorted(ids - RETIRED_PROVIDER_IDS),
            "table_names_sample": provider_names_in_markdown_tables(body)[:15],
        }

    hub_ids: set[str] = set()
    for h in hub_mentions.values():
        hub_ids |= set(h.get("provider_ids_from_aliases") or [])

    not_in_catalog = sorted(set(gaps) | hub_ids - catalog_ids - RETIRED_PROVIDER_IDS)
    hub_not_in_entitlements = sorted(hub_ids - entitlement_ids - RETIRED_PROVIDER_IDS)

    return {
        "generated_at": now,
        "category_a_provider_ids": category_a,
        "github_sync": {
            "mentioned_provider_ids": github.get("mentioned_provider_ids"),
            "retired_mentions_in_lists": github.get("retired_mentions_in_lists"),
            "errors": github.get("errors"),
        },
        "gaps_from_github_lists": gap_details,
        "hub_collections": hub_mentions,
        "provider_ids_not_in_catalog": not_in_catalog,
        "hub_provider_ids": sorted(hub_ids - RETIRED_PROVIDER_IDS),
        "hub_ids_not_in_entitlements": hub_not_in_entitlements,
        "discovery_web_directories": [
            {"id": d.get("id"), "url": d.get("url"), "notes": d.get("notes")}
            for d in meta.get("web_directories", [])
            if isinstance(d, dict)
        ],
        "recommended_agent_actions": [
            "For each gaps_from_github_lists row: official docs → probe-api → update free_tier_entitlements.json",
            "Do not promote directory rows (freellm.net, llmperks) to Category A without probe",
            "Re-run: privatemind research discover",
        ],
        "fetch_errors": errors,
    }


def write_latest_report(report: dict[str, Any], *, path: Path | None = None) -> Path:
    p = path or latest_report_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
        fh.write("\n")
    return p
