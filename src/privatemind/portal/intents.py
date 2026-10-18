"""Donor intent queue — append-only JSONL under data dir."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def intents_dir(data_dir: Path) -> Path:
    d = data_dir / "portal"
    d.mkdir(parents=True, exist_ok=True)
    return d


def intents_path(data_dir: Path) -> Path:
    return intents_dir(data_dir) / "donor_intents.jsonl"


def admin_note_path(data_dir: Path) -> Path:
    return intents_dir(data_dir) / "admin_note.txt"


def append_donor_intent(
    data_dir: Path,
    *,
    display_name: str,
    contact: str,
    offer: str,
    notes: str = "",
) -> dict[str, Any]:
    record = {
        "intent_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "display_name": display_name.strip(),
        "contact": contact.strip(),
        "offer": offer.strip(),
        "notes": notes.strip(),
        "status": "pending",
    }
    path = intents_path(data_dir)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return record


def list_donor_intents(data_dir: Path) -> list[dict[str, Any]]:
    path = intents_path(data_dir)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows
