"""Format audit rows for terminal display."""

from __future__ import annotations

from typing import Any


def _detail_snippet(detail: dict[str, Any], *, max_len: int = 120) -> str:
    if not detail:
        return ""
    parts: list[str] = []
    for key in (
        "task_id",
        "tool",
        "ok",
        "model",
        "mode",
        "activated",
        "level",
        "intent_id",
        "display_name",
        "offer",
        "account",
        "error",
        "executed",
        "state",
    ):
        if key in detail and detail[key] is not None and detail[key] != "":
            parts.append(f"{key}={detail[key]}")
    if not parts:
        parts = [f"{k}={v}" for k, v in list(detail.items())[:4]]
    text = " ".join(parts)
    if len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text


def format_event_line(event: dict[str, Any]) -> str:
    ts = event.get("created_at") or ""
    cat = event.get("category") or "?"
    detail = event.get("detail") or {}
    snippet = _detail_snippet(detail if isinstance(detail, dict) else {})
    if snippet:
        return f"{ts}  {cat:<22}  {snippet}"
    return f"{ts}  {cat}"
