import json
import socket
import threading
from pathlib import Path

from privatemind.audit.log import AuditLog
from privatemind.config import Settings
from privatemind.db import Database
from privatemind.memory.store import MemoryStore
from privatemind.worker.envelope import WireMessage, new_message
from privatemind.worker.hub import WorkerHub
from privatemind.worker.identity import NodeIdentity
from privatemind.worker.pairing_store import PairingStore
from privatemind.worker.service import WorkerTCPHandler, execute_job
import socketserver


def _start_test_worker(core: NodeIdentity, worker: NodeIdentity, port: int) -> threading.Thread:
    class Handler(WorkerTCPHandler):
        pass

    Handler.identity = worker
    Handler.core_fingerprint = core.fingerprint
    Handler.core_public_key_b64 = core.public_key_b64
    Handler.allowed_ops = ["compute_sha256"]

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True

    server = Server(("127.0.0.1", port), Handler)

    def run() -> None:
        server.serve_forever()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def _setup_hub(tmp_path: Path, port: int) -> tuple[WorkerHub, NodeIdentity, NodeIdentity, PairingStore]:
    core = NodeIdentity.generate("core")
    worker = NodeIdentity.generate("worker")
    db = Database(tmp_path / "mind.sqlite3")
    db.initialize()
    memory = MemoryStore(db)
    audit = AuditLog(db)
    pairing = PairingStore(db)
    pairing.pair_worker(
        fingerprint=worker.fingerprint,
        public_key_b64=worker.public_key_b64,
        label="test",
    )
    pairing.create_lease(
        lease_id="lease-1",
        worker_fingerprint=worker.fingerprint,
        operations=["compute_sha256"],
    )
    hub = WorkerHub(
        core_identity=core,
        pairing=pairing,
        memory=memory,
        audit=audit,
        host="127.0.0.1",
        port=port,
    )
    _start_test_worker(core, worker, port)
    return hub, core, worker, pairing


def test_delegate_compute_sha256_e2e(tmp_path: Path) -> None:
    hub, _, worker, _ = _setup_hub(tmp_path, 18765)
    out = hub.delegate_compute_sha256("hello", worker_fingerprint=worker.fingerprint)
    assert out["ok"] is True
    assert out["verification"]["authenticity_ok"] is True
    assert out["verification"]["correctness_status"] == "passed"


def test_false_signed_result_rejected(tmp_path: Path) -> None:
    core = NodeIdentity.generate("core")
    worker = NodeIdentity.generate("worker")
    port = 18766

    class EvilHandler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            raw = self.rfile.readline()
            incoming = WireMessage.from_dict(json.loads(raw.decode("utf-8")))
            job = incoming.payload["job"]
            body = job["body"]
            # Authentic signature but wrong hash
            bad = {"sha256": "0" * 64, "input_length": len(str(body.get("text", "")))}
            reply = new_message(
                sender=worker,
                recipient_id=core.fingerprint,
                payload_type="job_result",
                payload={"job_id": job["job_id"], "input_hash": job["input_hash"], "result": bad},
            )
            self.wfile.write((json.dumps(reply.to_dict()) + "\n").encode("utf-8"))

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True

    server = Server(("127.0.0.1", port), EvilHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    db = Database(tmp_path / "mind2.sqlite3")
    db.initialize()
    pairing = PairingStore(db)
    pairing.pair_worker(fingerprint=worker.fingerprint, public_key_b64=worker.public_key_b64)
    pairing.create_lease(lease_id="l1", worker_fingerprint=worker.fingerprint, operations=["compute_sha256"])
    hub = WorkerHub(
        core_identity=core,
        pairing=pairing,
        memory=MemoryStore(db),
        audit=AuditLog(db),
        host="127.0.0.1",
        port=port,
    )
    out = hub.delegate_compute_sha256("hello", worker_fingerprint=worker.fingerprint)
    assert out["ok"] is False
    assert out["verification"]["authenticity_ok"] is True
    assert out["verification"]["correctness_status"] == "failed"


def test_replay_rejected(tmp_path: Path) -> None:
    db = Database(tmp_path / "replay.sqlite3")
    db.initialize()
    pairing = PairingStore(db)
    assert pairing.record_replay("msg-1") is True
    assert pairing.record_replay("msg-1") is False


def test_delegate_survives_worker_restart(tmp_path: Path) -> None:
    hub, _, worker, _ = _setup_hub(tmp_path, 18768)
    assert hub.delegate_compute_sha256("once", worker_fingerprint=worker.fingerprint)["ok"] is True
    # Simulate restart: new hub same pairing store
    db = Database(tmp_path / "mind.sqlite3")
    hub2 = WorkerHub(
        core_identity=hub.core,
        pairing=PairingStore(db),
        memory=MemoryStore(db),
        audit=AuditLog(db),
        host="127.0.0.1",
        port=18768,
    )
    out = hub2.delegate_compute_sha256("twice", worker_fingerprint=worker.fingerprint)
    assert out["ok"] is True


def test_execute_job_allowlist() -> None:
    try:
        execute_job({"op": "run_shell"}, ["compute_sha256"])
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
