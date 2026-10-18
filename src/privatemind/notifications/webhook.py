import json
from typing import Any

import httpx


def post_assistance_webhook(url: str, *, question: str, request_id: str, context: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "event": "human_assistance_requested",
        "request_id": request_id,
        "question": question,
        "context": context,
    }
    try:
        resp = httpx.post(url, json=payload, timeout=15.0)
        return {"ok": resp.is_success, "status_code": resp.status_code}
    except httpx.HTTPError as exc:
        return {"ok": False, "error": str(exc)}
