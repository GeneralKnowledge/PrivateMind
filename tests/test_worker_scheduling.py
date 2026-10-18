import socketserver
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from privatemind.audit.log import AuditLog
from privatemind.db import Database
from privatemind.memory.store import MemoryStore
from privatemind.worker.hub import WorkerHub
from privatemind.worker.identity import NodeIdentity
from privatemind.worker.pairing_store import PairingStore
from privatemind.worker.scheduler import WorkerScheduler
from privatemind.worker.service import WorkerTCPHandler


def _start_worker(core: NodeIdentity, worker: NodeIdentity, port: int) -> None:
    class Handler(WorkerTCPHandler):
        pass

    Handler.identity = worker
    Handler.core_fingerprint = core.fingerprint
    Handler.core_public_key_b64 = core.public_key_b64
    Handler.allowed_ops = ["compute_sha256"]

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True

    server = Server(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()


def _hub(tmp_path: Path, core: NodeIdentity, worker: NodeIdentity, port: int) -> WorkerHub:
    db = Database(tmp_path / "sched.sqlite3")
    db.initialize()
    pairing = PairingStore(db)
    pairing.pair_worker(fingerprint=worker.fingerprint, public_key_b64=worker.public_key_b64)
    return WorkerHub(
        core_identity=core,
        pairing=pairing,
        memory=MemoryStore(db),
        audit=AuditLog(db),
        host="127.0.0.1",
        port=port,
    )


def test_max_jobs_enforced(tmp_path: Path) -> None:
    core = NodeIdentity.generate("core")
    worker = NodeIdentity.generate("worker")
    port = 18901
    _start_worker(core, worker, port)
    hub = _hub(tmp_path, core, worker, port)
    hub.pairing.create_lease(
        lease_id="cap-1",
        worker_fingerprint=worker.fingerprint,
        operations=["compute_sha256"],
        limits={"max_jobs": 1},
    )
    assert hub.delegate_compute_sha256("a", worker_fingerprint=worker.fingerprint)["ok"] is True
    blocked = hub.delegate_compute_sha256("b", worker_fingerprint=worker.fingerprint)
    assert blocked["ok"] is False
    assert blocked["error"] == "lease job budget exhausted"


def test_expired_lease_rejected(tmp_path: Path) -> None:
    core = NodeIdentity.generate("core")
    worker = NodeIdentity.generate("worker")
    port = 18902
    _start_worker(core, worker, port)
    hub = _hub(tmp_path, core, worker, port)
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    hub.pairing.create_lease(
        lease_id="exp-1",
        worker_fingerprint=worker.fingerprint,
        operations=["compute_sha256"],
        expires_at=past,
    )
    out = hub.delegate_compute_sha256("x", worker_fingerprint=worker.fingerprint)
    assert out["ok"] is False
    assert out["error"] == "lease expired"


def test_scheduler_round_robin(tmp_path: Path) -> None:
    core = NodeIdentity.generate("core")
    w1 = NodeIdentity.generate("worker")
    w2 = NodeIdentity.generate("worker")
    port1, port2 = 18903, 18904
    _start_worker(core, w1, port1)
    _start_worker(core, w2, port2)
    db = Database(tmp_path / "rr.sqlite3")
    db.initialize()
    pairing = PairingStore(db)
    pairing.pair_worker(fingerprint=w1.fingerprint, public_key_b64=w1.public_key_b64)
    pairing.pair_worker(fingerprint=w2.fingerprint, public_key_b64=w2.public_key_b64, label="second")
    pairing.create_lease(lease_id="l1", worker_fingerprint=w1.fingerprint, operations=["compute_sha256"])
    pairing.create_lease(lease_id="l2", worker_fingerprint=w2.fingerprint, operations=["compute_sha256"])

    hub = WorkerHub(
        core_identity=core,
        pairing=pairing,
        memory=MemoryStore(db),
        audit=AuditLog(db),
        host="127.0.0.1",
        port=port1,
    )
    # Point hub default port doesn't matter — peers have no endpoint; use delegate with fp from scheduler
    sched = WorkerScheduler(pairing)
    picks = [sched.select_worker("compute_sha256")["fingerprint"] for _ in range(4)]
    assert picks[0] != picks[1]
    assert picks[0] == picks[2]
    assert picks[1] == picks[3]

    # Wire endpoints for actual jobs
    pairing.pair_worker(
        fingerprint=w1.fingerprint,
        public_key_b64=w1.public_key_b64,
        endpoint_host="127.0.0.1",
        endpoint_port=port1,
    )
    pairing.pair_worker(
        fingerprint=w2.fingerprint,
        public_key_b64=w2.public_key_b64,
        endpoint_host="127.0.0.1",
        endpoint_port=port2,
    )
    a = hub.delegate_scheduled_compute_sha256("one")
    b = hub.delegate_scheduled_compute_sha256("two")
    assert a["ok"] and b["ok"]
    assert a["worker_fingerprint"] != b["worker_fingerprint"]


def test_contributor_scoped_schedule(tmp_path: Path) -> None:
    core = NodeIdentity.generate("core")
    w1 = NodeIdentity.generate("worker")
    w2 = NodeIdentity.generate("worker")
    port1, port2 = 18905, 18906
    _start_worker(core, w1, port1)
    _start_worker(core, w2, port2)
    db = Database(tmp_path / "contrib.sqlite3")
    db.initialize()
    pairing = PairingStore(db)
    cid = pairing.add_contributor(display_name="Alice")
    pairing.pair_worker(
        fingerprint=w1.fingerprint,
        public_key_b64=w1.public_key_b64,
        endpoint_host="127.0.0.1",
        endpoint_port=port1,
    )
    pairing.assign_worker_contributor(w1.fingerprint, cid)
    pairing.pair_worker(
        fingerprint=w2.fingerprint,
        public_key_b64=w2.public_key_b64,
        endpoint_host="127.0.0.1",
        endpoint_port=port2,
    )
    pairing.create_lease(lease_id="l1", worker_fingerprint=w1.fingerprint, operations=["compute_sha256"])
    pairing.create_lease(lease_id="l2", worker_fingerprint=w2.fingerprint, operations=["compute_sha256"])

    hub = WorkerHub(
        core_identity=core,
        pairing=pairing,
        memory=MemoryStore(db),
        audit=AuditLog(db),
    )
    out = hub.delegate_scheduled_compute_sha256("scoped", contributor_id=cid)
    assert out["ok"] is True
    assert out["worker_fingerprint"] == w1.fingerprint
