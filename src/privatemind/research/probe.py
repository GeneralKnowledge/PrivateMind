"""Lightweight probes for free-tier / OpenAI-compatible API endpoints."""

from __future__ import annotations

import httpx


def probe_openai_compatible(
    *,
    base_url: str,
    api_key: str | None = None,
    timeout_seconds: float = 20.0,
) -> dict:
    """GET /v1/models when possible; never log the full api_key."""
    base = base_url.rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    url = f"{base}/models"
    try:
        resp = httpx.get(url, headers=headers, timeout=timeout_seconds)
    except httpx.HTTPError as exc:
        return {"ok": False, "error": str(exc), "url": url}
    body_preview = (resp.text or "")[:2000]
    out: dict = {
        "ok": resp.is_success,
        "status_code": resp.status_code,
        "url": url,
    }
    if resp.is_success:
        try:
            data = resp.json()
            models = data.get("data") if isinstance(data, dict) else None
            if isinstance(models, list):
                out["model_count"] = len(models)
                out["sample_model_ids"] = [m.get("id") for m in models[:8] if isinstance(m, dict)]
        except Exception:  # noqa: BLE001
            out["body_preview"] = body_preview
    else:
        out["body_preview"] = body_preview
    return out


def probe_brave_web_search(
    *,
    api_key: str,
    query: str = "PrivateMind",
    timeout_seconds: float = 20.0,
) -> dict:
    """GET Brave web search; requires X-Subscription-Token (key not logged)."""
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {"X-Subscription-Token": api_key, "Accept": "application/json"}
    try:
        resp = httpx.get(
            url,
            params={"q": query, "count": 1},
            headers=headers,
            timeout=timeout_seconds,
        )
    except httpx.HTTPError as exc:
        return {"ok": False, "error": str(exc), "url": url}
    out: dict = {
        "ok": resp.is_success,
        "status_code": resp.status_code,
        "url": url,
    }
    if resp.is_success:
        try:
            data = resp.json()
            web = data.get("web") if isinstance(data, dict) else None
            results = web.get("results") if isinstance(web, dict) else None
            if isinstance(results, list) and results:
                out["sample_title"] = results[0].get("title")
                out["result_count"] = len(results)
        except Exception:  # noqa: BLE001
            out["body_preview"] = (resp.text or "")[:1500]
    else:
        out["body_preview"] = (resp.text or "")[:1500]
    return out
