import json
import uuid
from typing import Any

from privatemind.db import Database
from privatemind.executive.tasks import utc_now
from privatemind.security.redaction import redact, redact_mapping


class AuditLog:
    def __init__(self, db: Database) -> None:
        self._db = db

    def list_events(
        self,
        *,
        limit: int = 50,
        category: str | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        query = "SELECT id, category, detail_json, created_at FROM audit_events"
        params: list[Any] = []
        if category:
            query += " WHERE category = ?"
            params.append(category)
        query += " ORDER BY datetime(created_at) DESC, id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self._db.session() as conn:
            rows = conn.execute(query, params).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            detail_raw = row["detail_json"]
            try:
                detail = json.loads(detail_raw) if detail_raw else {}
            except json.JSONDecodeError:
                detail = {"_parse_error": True, "raw": detail_raw}
            out.append(
                {
                    "id": row["id"],
                    "category": row["category"],
                    "created_at": row["created_at"],
                    "detail": detail,
                }
            )
        return out

    def list_categories(self, *, limit: int = 100) -> list[str]:
        with self._db.session() as conn:
            rows = conn.execute(
                """
                SELECT category, COUNT(*) AS n FROM audit_events
                GROUP BY category ORDER BY n DESC LIMIT ?
                """,
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [str(row["category"]) for row in rows]

    def record(self, category: str, **detail: Any) -> str:
        event_id = str(uuid.uuid4())
        safe = redact_mapping({k: redact(str(v)) if isinstance(v, str) else v for k, v in detail.items()})
        with self._db.session() as conn:
            conn.execute(
                """
                INSERT INTO audit_events (id, category, detail_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (event_id, category, json.dumps(safe), utc_now()),
            )
        return event_id
