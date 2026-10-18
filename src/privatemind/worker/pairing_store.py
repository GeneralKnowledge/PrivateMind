import json
from typing import Any

from privatemind.db import Database
from privatemind.executive.tasks import utc_now


class PairingStore:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self._db.session() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS worker_peers (
                    fingerprint TEXT PRIMARY KEY,
                    public_key_b64 TEXT NOT NULL,
                    label TEXT NOT NULL DEFAULT '',
                    role TEXT NOT NULL DEFAULT 'worker',
                    trust_state TEXT NOT NULL DEFAULT 'paired',
                    paired_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS worker_leases (
                    lease_id TEXT PRIMARY KEY,
                    worker_fingerprint TEXT NOT NULL,
                    operations_json TEXT NOT NULL,
                    limits_json TEXT NOT NULL DEFAULT '{}',
                    expires_at TEXT,
                    revoked INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS worker_replay (
                    msg_id TEXT PRIMARY KEY,
                    seen_at TEXT NOT NULL
                );
                """
            )

    def pair_worker(self, *, fingerprint: str, public_key_b64: str, label: str = "") -> None:
        with self._db.session() as conn:
            conn.execute(
                """
                INSERT INTO worker_peers (fingerprint, public_key_b64, label, role, trust_state, paired_at)
                VALUES (?, ?, ?, 'worker', 'paired', ?)
                ON CONFLICT(fingerprint) DO UPDATE SET
                    public_key_b64 = excluded.public_key_b64,
                    label = excluded.label,
                    trust_state = 'paired',
                    paired_at = excluded.paired_at
                """,
                (fingerprint, public_key_b64, label, utc_now()),
            )

    def get_peer(self, fingerprint: str) -> dict[str, Any] | None:
        with self._db.session() as conn:
            row = conn.execute("SELECT * FROM worker_peers WHERE fingerprint = ?", (fingerprint,)).fetchone()
        return dict(row) if row else None

    def list_workers(self) -> list[dict[str, Any]]:
        with self._db.session() as conn:
            rows = conn.execute(
                "SELECT * FROM worker_peers WHERE role = 'worker' ORDER BY paired_at ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    def revoke_worker(self, fingerprint: str) -> bool:
        with self._db.session() as conn:
            cur = conn.execute(
                "UPDATE worker_peers SET trust_state = 'revoked' WHERE fingerprint = ?",
                (fingerprint,),
            )
            conn.execute(
                "UPDATE worker_leases SET revoked = 1 WHERE worker_fingerprint = ?",
                (fingerprint,),
            )
            return cur.rowcount > 0

    def record_replay(self, msg_id: str) -> bool:
        """Return False if msg_id already seen (replay)."""
        with self._db.session() as conn:
            exists = conn.execute("SELECT 1 FROM worker_replay WHERE msg_id = ?", (msg_id,)).fetchone()
            if exists:
                return False
            conn.execute(
                "INSERT INTO worker_replay (msg_id, seen_at) VALUES (?, ?)",
                (msg_id, utc_now()),
            )
            return True

    def create_lease(
        self,
        *,
        lease_id: str,
        worker_fingerprint: str,
        operations: list[str],
        limits: dict | None = None,
        expires_at: str | None = None,
    ) -> None:
        with self._db.session() as conn:
            conn.execute(
                """
                INSERT INTO worker_leases (
                    lease_id, worker_fingerprint, operations_json, limits_json,
                    expires_at, revoked, created_at
                ) VALUES (?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    lease_id,
                    worker_fingerprint,
                    json.dumps(operations),
                    json.dumps(limits or {}),
                    expires_at,
                    utc_now(),
                ),
            )

    def active_lease(self, worker_fingerprint: str, operation: str) -> dict[str, Any] | None:
        with self._db.session() as conn:
            rows = conn.execute(
                """
                SELECT * FROM worker_leases
                WHERE worker_fingerprint = ? AND revoked = 0
                ORDER BY created_at DESC
                """,
                (worker_fingerprint,),
            ).fetchall()
        for row in rows:
            ops = json.loads(row["operations_json"])
            if operation in ops:
                return dict(row)
        return None
