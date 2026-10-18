import threading
import time
from pathlib import Path

import socketserver

from privatemind.audit.log import AuditLog
from privatemind.db import Database
from privatemind.memory.store import MemoryStore
from privatemind.worker.hub import WorkerHub
from privatemind.worker.identity import NodeIdentity
from privatemind.worker.mtls import build_server_ssl_context, core_client_paths, worker_server_paths
from privatemind.worker.pairing_store import PairingStore
from privatemind.worker.pki import init_dev_pki
from privatemind.worker.service import WorkerTCPHandler


def _start_mtls_worker(core: NodeIdentity, worker: NodeIdentity, pki_dir: Path, port: int) -> None:
    class Handler(WorkerTCPHandler):
        pass

    Handler.identity = worker
    Handler.core_fingerprint = core.fingerprint
    Handler.core_public_key_b64 = core.public_key_b64
    Handler.allowed_ops = ["compute_sha256"]

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True

    ssl_ctx = build_server_ssl_context(worker_server_paths(pki_dir))

    class SecureServer(Server):
        def get_request(self):
            client, addr = self.socket.accept()
            return ssl_ctx.wrap_socket(client, server_side=True), addr

    server = SecureServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()


def test_mtls_delegate_e2e(tmp_path: Path) -> None:
    init_dev_pki(tmp_path / "mtls", server_sans=["127.0.0.1", "localhost"])
    core = NodeIdentity.generate("core")
    worker = NodeIdentity.generate("worker")
    port = 18865

    db = Database(tmp_path / "mind.sqlite3")
    db.initialize()
    pairing = PairingStore(db)
    pairing.pair_worker(
        fingerprint=worker.fingerprint,
        public_key_b64=worker.public_key_b64,
        endpoint_host="127.0.0.1",
        endpoint_port=port,
        use_mtls=True,
    )
    pairing.create_lease(lease_id="l1", worker_fingerprint=worker.fingerprint, operations=["compute_sha256"])

    _start_mtls_worker(core, worker, tmp_path / "mtls", port)
    time.sleep(0.15)

    hub = WorkerHub(
        core_identity=core,
        pairing=pairing,
        memory=MemoryStore(db),
        audit=AuditLog(db),
        mtls_paths=core_client_paths(tmp_path / "mtls"),
        default_use_mtls=True,
    )
    out = hub.delegate_compute_sha256("mtls-test", worker_fingerprint=worker.fingerprint)
    assert out["ok"] is True
    assert out["verification"]["correctness_status"] == "passed"
