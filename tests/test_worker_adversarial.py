import json
import socketserver
import threading
from pathlib import Path

from privatemind.audit.log import AuditLog
from privatemind.db import Database
from privatemind.memory.store import MemoryStore
from privatemind.worker.envelope import WireMessage, new_message
from privatemind.worker.hub import WorkerHub
from privatemind.worker.identity import NodeIdentity
from privatemind.worker.pairing_store import PairingStore
from privatemind.worker.service import WorkerTCPHandler
import socketserver


def _start_test_worker(core: NodeIdentity, worker: NodeIdentity, port: int) -> None:
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


def _setup_good_hub(tmp_path: Path, port: int) -> tuple[WorkerHub, NodeIdentity, NodeIdentity, PairingStore]:
    core = NodeIdentity.generate("core")
    worker = NodeIdentity.generate("worker")
    hub = _hub_on_port(tmp_path, core, worker, port)
    _start_test_worker(core, worker, port)
    return hub, core, worker, hub.pairing


def _evil_server(core: NodeIdentity, worker: NodeIdentity, port: int, *, mode: str) -> None:
    class EvilHandler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            raw = self.rfile.readline()
            incoming = WireMessage.from_dict(json.loads(raw.decode("utf-8")))
            job = incoming.payload["job"]
            body = job["body"]
            text = str(body.get("text", ""))
            if mode == "wrong_hash":
                bad = {"sha256": "0" * 64, "input_length": len(text)}
            elif mode == "wrong_input_hash_field":
                bad = {
                    "sha256": __import__("hashlib").sha256(text.encode()).hexdigest(),
                    "input_length": len(text),
                }
            else:
                raise ValueError(mode)
            reply = new_message(
                sender=worker,
                recipient_id=core.fingerprint,
                payload_type="job_result",
                payload={
                    "job_id": job["job_id"],
                    "input_hash": "0" * 64 if mode == "wrong_input_hash_field" else job["input_hash"],
                    "result": bad,
                },
            )
            self.wfile.write((json.dumps(reply.to_dict()) + "\n").encode("utf-8"))

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True

    server = Server(("127.0.0.1", port), EvilHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()


def _hub_on_port(tmp_path: Path, core: NodeIdentity, worker: NodeIdentity, port: int, **hub_kw) -> WorkerHub:
    db = Database(tmp_path / f"m-{port}.sqlite3")
    db.initialize()
    pairing = PairingStore(db)
    pairing.pair_worker(fingerprint=worker.fingerprint, public_key_b64=worker.public_key_b64)
    pairing.create_lease(lease_id="l1", worker_fingerprint=worker.fingerprint, operations=["compute_sha256"])
    return WorkerHub(
        core_identity=core,
        pairing=pairing,
        memory=MemoryStore(db),
        audit=AuditLog(db),
        host="127.0.0.1",
        port=port,
        **hub_kw,
    )


def test_input_hash_mismatch_rejected(tmp_path: Path) -> None:
    core = NodeIdentity.generate("core")
    worker = NodeIdentity.generate("worker")
    port = 18801
    _evil_server(core, worker, port, mode="wrong_input_hash_field")
    hub = _hub_on_port(tmp_path, core, worker, port)
    out = hub.delegate_compute_sha256("hello", worker_fingerprint=worker.fingerprint)
    assert out["ok"] is False
    assert out["verification"]["input_hash_ok"] is False
    assert "input_hash_mismatch" in out["verification"]["rejection_reasons"]


def test_auto_quarantine_after_failures(tmp_path: Path) -> None:
    core = NodeIdentity.generate("core")
    worker = NodeIdentity.generate("worker")
    port = 18802
    _evil_server(core, worker, port, mode="wrong_hash")
    hub = _hub_on_port(tmp_path, core, worker, port, quarantine_failure_threshold=2)
    assert hub.delegate_compute_sha256("a", worker_fingerprint=worker.fingerprint)["ok"] is False
    peer = hub.pairing.get_peer(worker.fingerprint)
    assert peer and peer["trust_state"] == "paired"
    assert hub.delegate_compute_sha256("b", worker_fingerprint=worker.fingerprint)["ok"] is False
    peer = hub.pairing.get_peer(worker.fingerprint)
    assert peer and peer["trust_state"] == "quarantined"
    blocked = hub.delegate_compute_sha256("c", worker_fingerprint=worker.fingerprint)
    assert blocked["ok"] is False
    assert blocked["error"] == "worker quarantined"


def test_restricted_worker_never_auto_accepts(tmp_path: Path) -> None:
    hub, _, worker, pairing = _setup_good_hub(tmp_path, 18803)
    pairing.restrict_worker(worker.fingerprint)
    out = hub.delegate_compute_sha256("hello", worker_fingerprint=worker.fingerprint)
    assert out["verification"]["correctness_status"] == "passed"
    assert out["ok"] is False
    assert out["verification"]["accepted"] is False
    peer = pairing.get_peer(worker.fingerprint)
    assert peer and peer["trust_state"] == "restricted"


def test_release_quarantine_restores_delegate(tmp_path: Path) -> None:
    hub, _, worker, pairing = _setup_good_hub(tmp_path, 18804)
    pairing.quarantine_worker(worker.fingerprint)
    assert hub.delegate_compute_sha256("x", worker_fingerprint=worker.fingerprint)["error"] == "worker quarantined"
    pairing.release_quarantine(worker.fingerprint)
    out = hub.delegate_compute_sha256("hello", worker_fingerprint=worker.fingerprint)
    assert out["ok"] is True
