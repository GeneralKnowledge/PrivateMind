import json
import uuid
from enum import Enum
from typing import Any

from privatemind.db import Database
from privatemind.executive.tasks import utc_now


class HumanRequestStatus(str, Enum):
    PENDING = "pending"
    ANSWERED = "answered"
    DISMISSED = "dismissed"


class HumanAssistance:
    def __init__(self, db: Database, *, on_created=None) -> None:
        self._db = db
        self._on_created = on_created

    def create_request(
        self,
        question: str,
        *,
        context: dict[str, Any] | None = None,
        task_id: str | None = None,
    ) -> str:
        req_id = str(uuid.uuid4())
        with self._db.session() as conn:
            conn.execute(
                """
                INSERT INTO human_requests (
                    id, task_id, question, context_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    req_id,
                    task_id,
                    question,
                    json.dumps(context or {}),
                    HumanRequestStatus.PENDING.value,
                    utc_now(),
                ),
            )
        if self._on_created:
            self._on_created(req_id, question, context or {})
        return req_id

    def list_pending(self) -> list[dict]:
        with self._db.session() as conn:
            rows = conn.execute(
                "SELECT * FROM human_requests WHERE status = ? ORDER BY created_at ASC",
                (HumanRequestStatus.PENDING.value,),
            ).fetchall()
        return [dict(r) for r in rows]

    def answer(self, request_id: str, response: str) -> bool:
        with self._db.session() as conn:
            cur = conn.execute(
                """
                UPDATE human_requests SET status = ?, response = ?, answered_at = ?
                WHERE id = ? AND status = ?
                """,
                (
                    HumanRequestStatus.ANSWERED.value,
                    response,
                    utc_now(),
                    request_id,
                    HumanRequestStatus.PENDING.value,
                ),
            )
            return cur.rowcount > 0

    def get(self, request_id: str) -> dict | None:
        with self._db.session() as conn:
            row = conn.execute("SELECT * FROM human_requests WHERE id = ?", (request_id,)).fetchone()
        return dict(row) if row else None
