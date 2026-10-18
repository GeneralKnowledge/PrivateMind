import json
import uuid
from typing import Any

from privatemind.db import Database
from privatemind.executive.tasks import utc_now
from privatemind.security.redaction import redact, redact_mapping


class AuditLog:
    def __init__(self, db: Database) -> None:
        self._db = db

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
