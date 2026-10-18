import json
import uuid
from enum import Enum
from typing import Any

from privatemind.db import Database
from privatemind.executive.tasks import utc_now


class ToolRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ToolRequestStore:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self._db.session() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tool_requests (
                    id TEXT PRIMARY KEY,
                    tool_name TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    justification TEXT NOT NULL DEFAULT '',
                    risk_notes TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    task_id TEXT,
                    capability_id TEXT,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT
                )
                """
            )

    def create(
        self,
        *,
        tool_name: str,
        purpose: str,
        justification: str = "",
        risk_notes: str = "",
        task_id: str | None = None,
    ) -> str:
        req_id = str(uuid.uuid4())
        with self._db.session() as conn:
            conn.execute(
                """
                INSERT INTO tool_requests (
                    id, tool_name, purpose, justification, risk_notes,
                    status, task_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    req_id,
                    tool_name,
                    purpose,
                    justification,
                    risk_notes,
                    ToolRequestStatus.PENDING.value,
                    task_id,
                    utc_now(),
                ),
            )
        return req_id

    def list_pending(self) -> list[dict[str, Any]]:
        with self._db.session() as conn:
            rows = conn.execute(
                "SELECT * FROM tool_requests WHERE status = ? ORDER BY created_at ASC",
                (ToolRequestStatus.PENDING.value,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get(self, request_id: str) -> dict[str, Any] | None:
        with self._db.session() as conn:
            row = conn.execute("SELECT * FROM tool_requests WHERE id = ?", (request_id,)).fetchone()
        return dict(row) if row else None

    def approve(self, request_id: str, *, capability_id: str) -> bool:
        with self._db.session() as conn:
            cur = conn.execute(
                """
                UPDATE tool_requests SET status = ?, capability_id = ?, resolved_at = ?
                WHERE id = ? AND status = ?
                """,
                (
                    ToolRequestStatus.APPROVED.value,
                    capability_id,
                    utc_now(),
                    request_id,
                    ToolRequestStatus.PENDING.value,
                ),
            )
            return cur.rowcount > 0

    def reject(self, request_id: str) -> bool:
        with self._db.session() as conn:
            cur = conn.execute(
                """
                UPDATE tool_requests SET status = ?, resolved_at = ?
                WHERE id = ? AND status = ?
                """,
                (ToolRequestStatus.REJECTED.value, utc_now(), request_id, ToolRequestStatus.PENDING.value),
            )
            return cur.rowcount > 0
