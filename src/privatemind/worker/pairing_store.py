import json
import uuid
from typing import Any

from privatemind.db import Database
from privatemind.executive.tasks import utc_now
from privatemind.worker.lease_util import lease_expired, lease_jobs_remaining, lease_usable
from privatemind.worker.trust import can_delegate


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
                CREATE TABLE IF NOT EXISTS worker_contributors (
                    contributor_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    contact TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS worker_schedule_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    round_robin_cursor INTEGER NOT NULL DEFAULT 0
                );
                INSERT OR IGNORE INTO worker_schedule_state (id, round_robin_cursor) VALUES (1, 0);
                """
            )
            self._migrate_worker_peers(conn)
            self._migrate_worker_leases(conn)

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
        if "contributor_id" not in cols:
            conn.execute("ALTER TABLE worker_peers ADD COLUMN contributor_id TEXT")

    def _migrate_worker_leases(self, conn) -> None:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(worker_leases)")}
        if "jobs_used" not in cols:
            conn.execute("ALTER TABLE worker_leases ADD COLUMN jobs_used INTEGER NOT NULL DEFAULT 0")
        if "contributor_id" not in cols:
            conn.execute("ALTER TABLE worker_leases ADD COLUMN contributor_id TEXT")

    def add_contributor(
        self,
        *,
        display_name: str,
        contact: str = "",
        notes: str = "",
        contributor_id: str | None = None,
    ) -> str:
        cid = contributor_id or str(uuid.uuid4())
        with self._db.session() as conn:
            conn.execute(
                """
                INSERT INTO worker_contributors (contributor_id, display_name, contact, notes, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (cid, display_name, contact, notes, utc_now()),
            )
        return cid

    def list_contributors(self) -> list[dict[str, Any]]:
        with self._db.session() as conn:
            rows = conn.execute(
                "SELECT * FROM worker_contributors ORDER BY created_at ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_contributor(self, contributor_id: str) -> dict[str, Any] | None:
        with self._db.session() as conn:
            row = conn.execute(
                "SELECT * FROM worker_contributors WHERE contributor_id = ?",
                (contributor_id,),
            ).fetchone()
        return dict(row) if row else None

    def assign_worker_contributor(self, worker_fingerprint: str, contributor_id: str) -> bool:
        if not self.get_contributor(contributor_id):
            return False
        with self._db.session() as conn:
            cur = conn.execute(
                "UPDATE worker_peers SET contributor_id = ? WHERE fingerprint = ?",
                (contributor_id, worker_fingerprint),
            )
            return cur.rowcount > 0

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
        contributor_id: str | None = None,
    ) -> None:
        if contributor_id and not self.get_contributor(contributor_id):
            raise ValueError(f"unknown contributor: {contributor_id}")
        with self._db.session() as conn:
            conn.execute(
                """
                INSERT INTO worker_leases (
                    lease_id, worker_fingerprint, operations_json, limits_json,
                    expires_at, revoked, created_at, jobs_used, contributor_id
                ) VALUES (?, ?, ?, ?, ?, 0, ?, 0, ?)
                """,
                (
                    lease_id,
                    worker_fingerprint,
                    json.dumps(operations),
                    json.dumps(limits or {}),
                    expires_at,
                    utc_now(),
                    contributor_id,
                ),
            )

    def list_leases(self, worker_fingerprint: str | None = None) -> list[dict[str, Any]]:
        with self._db.session() as conn:
            if worker_fingerprint:
                rows = conn.execute(
                    "SELECT * FROM worker_leases WHERE worker_fingerprint = ? ORDER BY created_at DESC",
                    (worker_fingerprint,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM worker_leases ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def consume_lease_job(self, lease_id: str) -> bool:
        with self._db.session() as conn:
            cur = conn.execute(
                "UPDATE worker_leases SET jobs_used = jobs_used + 1 WHERE lease_id = ? AND revoked = 0",
                (lease_id,),
            )
            return cur.rowcount > 0

    def lease_delegation_error(self, worker_fingerprint: str, operation: str) -> str:
        with self._db.session() as conn:
            rows = conn.execute(
                """
                SELECT * FROM worker_leases
                WHERE worker_fingerprint = ? AND revoked = 0
                ORDER BY created_at DESC
                """,
                (worker_fingerprint,),
            ).fetchall()
        saw_op = False
        for row in rows:
            lease = dict(row)
            ops = json.loads(lease["operations_json"])
            if operation not in ops:
                continue
            saw_op = True
            if lease_usable(lease, operation):
                return ""
            if lease_expired(lease):
                return "lease expired"
            remaining = lease_jobs_remaining(lease)
            if remaining is not None and remaining <= 0:
                return "lease job budget exhausted"
        if saw_op:
            return "no usable lease for operation"
        return "no active lease for operation"

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
            lease = dict(row)
            if lease_usable(lease, operation):
                return lease
        return None

    def worker_reputation(self, worker_fingerprint: str, *, window: int = 20) -> dict[str, Any]:
        with self._db.session() as conn:
            rows = conn.execute(
                """
                SELECT accepted, correctness_status FROM worker_verification_events
                WHERE worker_fingerprint = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (worker_fingerprint, window),
            ).fetchall()
        if not rows:
            return {"score": 1.0, "samples": 0, "accepted_rate": None}
        accepted = sum(int(r["accepted"]) for r in rows)
        samples = len(rows)
        rate = accepted / samples
        peer = self.get_peer(worker_fingerprint) or {}
        failures = int(peer.get("consecutive_failures") or 0)
        penalty = min(0.5, failures * 0.1)
        score = max(0.0, min(1.0, rate - penalty))
        return {"score": score, "samples": samples, "accepted_rate": rate, "consecutive_failures": failures}

    def next_schedule_index(self, pool_size: int) -> int:
        if pool_size <= 0:
            return 0
        with self._db.session() as conn:
            row = conn.execute("SELECT round_robin_cursor FROM worker_schedule_state WHERE id = 1").fetchone()
            cursor = int(row["round_robin_cursor"]) if row else 0
            idx = cursor % pool_size
            conn.execute(
                "UPDATE worker_schedule_state SET round_robin_cursor = ? WHERE id = 1",
                (cursor + 1,),
            )
            return idx

    def list_delegatable_workers(
        self,
        operation: str,
        *,
        contributor_id: str | None = None,
    ) -> list[dict[str, Any]]:
        workers = self.list_workers()
        eligible: list[dict[str, Any]] = []
        for worker in workers:
            if not can_delegate(str(worker.get("trust_state") or "")):
                continue
            if contributor_id and worker.get("contributor_id") != contributor_id:
                continue
            if self.active_lease(worker["fingerprint"], operation):
                eligible.append(worker)

        def _sort_key(w: dict[str, Any]) -> tuple:
            rep = self.worker_reputation(w["fingerprint"])
            return (-float(rep["score"]), str(w.get("paired_at") or ""))

        eligible.sort(key=_sort_key)
        return eligible
