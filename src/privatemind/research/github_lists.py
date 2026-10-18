"""Fetch and scan curated GitHub lists for free LLM provider mentions."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx

from privatemind.research.provider_catalog import catalog_provider_ids, load_catalog

_SOURCES_REL = Path("docs/data/free_tier_github_sources.json")

# Still appear in old GitHub README lists but must not be routed (see free_tier_entitlements.json retired).
RETIRED_PROVIDER_IDS: frozenset[str] = frozenset({"github_models"})

# Substrings matched case-insensitively in fetched markdown → catalog provider_id.
PROVIDER_ALIASES: tuple[tuple[str, str], ...] = (
    ("aion labs", "aion_labs"),
    ("cohere", "cohere"),
    ("google ai studio", "google_gemini"),
    ("google gemini", "google_gemini"),
    ("gemini api", "google_gemini"),
    ("mistral", "mistral"),
    ("codestral", "mistral"),
    ("z.ai", "z_ai"),
    ("zhipu", "z_ai"),
    ("cloudflare workers ai", "cloudflare_workers_ai"),
    ("workers ai", "cloudflare_workers_ai"),
    ("groq", "groq"),
    ("groqcloud", "groq"),
    ("hugging face", "huggingface"),
    ("huggingface", "huggingface"),
    ("kilo gateway", "kilo"),
    ("kilo code", "kilo"),
    ("llm7", "llm7"),
    ("modelscope", "modelscope"),
    ("nvidia nim", "nvidia_nim"),
    ("build.nvidia.com", "nvidia_nim"),
    ("ollama cloud", "ollama_cloud"),
    ("openrouter", "openrouter"),
    ("ovhcloud ai endpoints", "ovhcloud_ai_endpoints"),
    ("ovh ai endpoints", "ovhcloud_ai_endpoints"),
    ("siliconflow", "siliconflow"),
    ("sambanova", "sambanova_cloud"),
    ("sambanova cloud", "sambanova_cloud"),
    ("unorouter", "unorouter"),
    ("github models", "github_models"),
    ("pollinations", "pollinations_ai"),
    ("cerebras", "cerebras"),
    ("fireworks", "fireworks_ai"),
    ("vercel ai gateway", "vercel_ai_gateway"),
    ("scaleway generative", "scaleway_genai"),
    ("deepseek", "deepseek_api"),
    ("pollinations", "pollinations_ai"),
)


def sources_path() -> Path:
    return Path(__file__).resolve().parents[3] / _SOURCES_REL


def load_github_sources(*, path: Path | None = None) -> dict[str, Any]:
    p = path or sources_path()
    with p.open(encoding="utf-8") as fh:
        data = json.load(fh)
    sources = data.get("sources")
    if not isinstance(sources, list):
        raise ValueError("github sources file missing sources array")
    return data


def raw_github_url(*, repo: str, path: str, branch: str = "main") -> str:
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"


def fetch_github_markdown(
    *,
    repo: str,
    path: str,
    branch: str = "main",
    timeout_seconds: float = 30.0,
    raw_url: str | None = None,
) -> str:
    url = raw_url or raw_github_url(repo=repo, path=path, branch=branch)
    resp = httpx.get(url, timeout=timeout_seconds, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


def provider_ids_in_text(text: str) -> set[str]:
    lower = text.lower()
    found: set[str] = set()
    for needle, provider_id in PROVIDER_ALIASES:
        if needle in lower:
            found.add(provider_id)
    return found


def markdown_section_titles(text: str) -> list[str]:
    titles: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^#{2,3}\s+(.+?)\s*$", line.strip())
        if m:
            titles.append(m.group(1).strip())
    return titles


def sync_github_sources(
    *,
    source_id: str | None = None,
    catalog: dict[str, Any] | None = None,
    fetch: bool = True,
) -> dict[str, Any]:
    meta = load_github_sources()
    cat = catalog if catalog is not None else load_catalog()
    catalog_ids = catalog_provider_ids(cat)

    by_source: dict[str, Any] = {}
    all_mentioned: set[str] = set()
    errors: dict[str, str] = {}

    for src in meta["sources"]:
        if not isinstance(src, dict):
            continue
        sid = str(src.get("id") or "")
        if source_id and sid != source_id:
            continue
        repo = str(src.get("repo") or "")
        path = str(src.get("path") or "README.md")
        branch = str(src.get("branch") or "main")
        skip_fetch = bool(src.get("skip_fetch"))
        override_raw = str(src.get("raw_url") or "") or None
        web_url = str(src.get("web_url") or "")
        if skip_fetch and not override_raw:
            by_source[sid] = {
                "repo": repo,
                "skipped_fetch": True,
                "web_url": web_url or (f"https://github.com/{repo}" if repo else ""),
                "provider_ids": [],
                "section_headings_sample": [],
            }
            continue
        if not repo and not override_raw:
            continue
        if fetch:
            try:
                body = fetch_github_markdown(
                    repo=repo,
                    path=path,
                    branch=branch,
                    raw_url=override_raw,
                )
            except httpx.HTTPError as exc:
                errors[sid] = str(exc)
                continue
        else:
            body = ""
        ids = provider_ids_in_text(body) if body else set()
        all_mentioned |= ids
        by_source[sid] = {
            "repo": repo,
            "url": override_raw or (raw_github_url(repo=repo, path=path, branch=branch) if repo else ""),
            "web_url": web_url,
            "provider_ids": sorted(ids),
            "section_headings_sample": markdown_section_titles(body)[:12] if body else [],
        }

    retired_mentioned = sorted(all_mentioned & RETIRED_PROVIDER_IDS)
    active_mentioned = all_mentioned - RETIRED_PROVIDER_IDS
    in_github_not_catalog = sorted(active_mentioned - catalog_ids)

    return {
        "schema_version_sources": meta.get("schema_version"),
        "fetched": fetch,
        "source_filter": source_id,
        "mentioned_provider_ids": sorted(active_mentioned),
        "retired_mentions_in_lists": retired_mentioned,
        "in_github_lists_not_in_catalog": in_github_not_catalog,
        "in_catalog_not_seen_in_github_scan": sorted(catalog_ids - all_mentioned),
        "by_source": by_source,
        "errors": errors,
    }
