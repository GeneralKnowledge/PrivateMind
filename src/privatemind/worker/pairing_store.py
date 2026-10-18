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
                    paired_at TEXT NOT NULL,
                    endpoint_host TEXT,
                    endpoint_port INTEGER,
                    use_mtls INTEGER NOT NULL DEFAULT 0
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
                CREATE TABLE IF NOT EXISTS worker_verification_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    worker_fingerprint TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    accepted INTEGER NOT NULL,
                    authenticity_ok INTEGER NOT NULL,
                    correctness_status TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                """
            )
            self._migrate_worker_peers(conn)

    def _migrate_worker_peers(self, conn) -> None:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(worker_peers)")}
        if "endpoint_host" not in cols:
            conn.execute("ALTER TABLE worker_peers ADD COLUMN endpoint_host TEXT")
        if "endpoint_port" not in cols:
            conn.execute("ALTER TABLE worker_peers ADD COLUMN endpoint_port INTEGER")
        if "use_mtls" not in cols:
            conn.execute("ALTER TABLE worker_peers ADD COLUMN use_mtls INTEGER NOT NULL DEFAULT 0")
        if "consecutive_failures" not in cols:
            conn.execute("ALTER TABLE worker_peers ADD COLUMN consecutive_failures INTEGER NOT NULL DEFAULT 0")
        if "quarantined_at" not in cols:
            conn.execute("ALTER TABLE worker_peers ADD COLUMN quarantined_at TEXT")

    def pair_worker(
        self,
        *,
        fingerprint: str,
        public_key_b64: str,
        label: str = "",
        endpoint_host: str | None = None,
        endpoint_port: int | None = None,
        use_mtls: bool = False,
    ) -> None:
        with self._db.session() as conn:
            conn.execute(
                """
                INSERT INTO worker_peers (
                    fingerprint, public_key_b64, label, role, trust_state, paired_at,
                    endpoint_host, endpoint_port, use_mtls
                )
                VALUES (?, ?, ?, 'worker', 'paired', ?, ?, ?, ?)
                ON CONFLICT(fingerprint) DO UPDATE SET
                    public_key_b64 = excluded.public_key_b64,
                    label = excluded.label,
                    trust_state = 'paired',
                    paired_at = excluded.paired_at,
                    endpoint_host = COALESCE(excluded.endpoint_host, worker_peers.endpoint_host),
                    endpoint_port = COALESCE(excluded.endpoint_port, worker_peers.endpoint_port),
                    use_mtls = excluded.use_mtls
                """,
                (
                    fingerprint,
                    public_key_b64,
                    label,
                    utc_now(),
                    endpoint_host,
                    endpoint_port,
                    1 if use_mtls else 0,
                ),
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

    def set_trust_state(self, fingerprint: str, trust_state: str) -> bool:
        with self._db.session() as conn:
            cur = conn.execute(
                "UPDATE worker_peers SET trust_state = ? WHERE fingerprint = ?",
                (trust_state, fingerprint),
            )
            return cur.rowcount > 0

    def quarantine_worker(self, fingerprint: str, *, reason: str = "operator") -> bool:
        with self._db.session() as conn:
            cur = conn.execute(
                """
                UPDATE worker_peers
                SET trust_state = 'quarantined', quarantined_at = ?
                WHERE fingerprint = ?
                """,
                (utc_now(), fingerprint),
            )
            return cur.rowcount > 0

    def release_quarantine(self, fingerprint: str) -> bool:
        with self._db.session() as conn:
            cur = conn.execute(
                """
                UPDATE worker_peers
                SET trust_state = 'paired', quarantined_at = NULL, consecutive_failures = 0
                WHERE fingerprint = ? AND trust_state = 'quarantined'
                """,
                (fingerprint,),
            )
            return cur.rowcount > 0

    def restrict_worker(self, fingerprint: str) -> bool:
        return self.set_trust_state(fingerprint, "restricted")

    def restore_paired(self, fingerprint: str) -> bool:
        with self._db.session() as conn:
            cur = conn.execute(
                """
                UPDATE worker_peers
                SET trust_state = 'paired', consecutive_failures = 0
                WHERE fingerprint = ? AND trust_state IN ('restricted', 'paired')
                """,
                (fingerprint,),
            )
            return cur.rowcount > 0

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

    def record_verification_outcome(
        self,
        *,
        worker_fingerprint: str,
        job_id: str,
        accepted: bool,
        authenticity_ok: bool,
        correctness_status: str,
        failure_threshold: int,
    ) -> dict[str, Any]:
        """Persist event; auto-quarantine after consecutive failed verifications."""
        quarantined = False
        with self._db.session() as conn:
            conn.execute(
                """
                INSERT INTO worker_verification_events (
                    worker_fingerprint, job_id, accepted, authenticity_ok,
                    correctness_status, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    worker_fingerprint,
                    job_id,
                    1 if accepted else 0,
                    1 if authenticity_ok else 0,
                    correctness_status,
                    utc_now(),
                ),
            )
            if accepted:
                conn.execute(
                    "UPDATE worker_peers SET consecutive_failures = 0 WHERE fingerprint = ?",
                    (worker_fingerprint,),
                )
            else:
                conn.execute(
                    """
                    UPDATE worker_peers
                    SET consecutive_failures = consecutive_failures + 1
                    WHERE fingerprint = ?
                    """,
                    (worker_fingerprint,),
                )
                row = conn.execute(
                    "SELECT consecutive_failures, trust_state FROM worker_peers WHERE fingerprint = ?",
                    (worker_fingerprint,),
                ).fetchone()
                if row and row["trust_state"] == "paired":
                    failures = int(row["consecutive_failures"])
                    if failures >= failure_threshold:
                        conn.execute(
                            """
                            UPDATE worker_peers
                            SET trust_state = 'quarantined', quarantined_at = ?
                            WHERE fingerprint = ?
                            """,
                            (utc_now(), worker_fingerprint),
                        )
                        quarantined = True
        return {"quarantined": quarantined}

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
