import json
import uuid
from typing import Any

from privatemind.db import Database
from privatemind.executive.tasks import utc_now
from privatemind.trust import Provenance, TrustLevel


class MemoryStore:
    """Structured durable memory; writes only through trusted core paths."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def upsert(
        self,
        *,
        kind: str,
        key: str,
        content: str,
        provenance: Provenance,
        trust_level: TrustLevel,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        entry_id = str(uuid.uuid4())
        now = utc_now()
        meta = json.dumps(metadata or {})
        with self._db.session() as conn:
            existing = conn.execute(
                "SELECT id FROM memory_entries WHERE kind = ? AND key = ?", (kind, key)
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE memory_entries SET
                        content = ?, provenance = ?, trust_level = ?,
                        metadata_json = ?, updated_at = ?
                    WHERE kind = ? AND key = ?
                    """,
                    (
                        content,
                        provenance.value,
                        trust_level.value,
                        meta,
                        now,
                        kind,
                        key,
                    ),
                )
                return existing["id"]
            conn.execute(
                """
                INSERT INTO memory_entries (
                    id, kind, key, content, provenance, trust_level,
                    metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id,
                    kind,
                    key,
                    content,
                    provenance.value,
                    trust_level.value,
                    meta,
                    now,
                    now,
                ),
            )
        return entry_id

    def get(self, kind: str, key: str) -> dict | None:
        with self._db.session() as conn:
            row = conn.execute(
                "SELECT * FROM memory_entries WHERE kind = ? AND key = ?", (kind, key)
            ).fetchone()
        return dict(row) if row else None

    def search(self, *, kind: str | None = None, query: str | None = None, limit: int = 20) -> list[dict]:
        sql = "SELECT * FROM memory_entries WHERE 1=1"
        params: list[Any] = []
        if kind:
            sql += " AND kind = ?"
            params.append(kind)
        if query:
            sql += " AND (key LIKE ? OR content LIKE ?)"
            params.extend([f"%{query}%", f"%{query}%"])
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self._db.session() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
