import hashlib
import json
import socketserver
from typing import Any

from privatemind.worker.envelope import WireMessage, new_message
from privatemind.worker.identity import NodeIdentity
from privatemind.worker.verifier import input_hash


def execute_job(body: dict[str, Any], allowed: list[str]) -> dict[str, Any]:
    op = str(body.get("op", ""))
    if op not in allowed:
        raise ValueError(f"operation not allowed: {op}")
    if op == "compute_sha256":
        text = str(body.get("text", ""))
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return {"sha256": digest, "input_length": len(text)}
    raise ValueError(f"unsupported op: {op}")


class WorkerTCPHandler(socketserver.StreamRequestHandler):
    identity: NodeIdentity
    core_fingerprint: str
    core_public_key_b64: str
    allowed_ops: list[str]

    def handle(self) -> None:
        raw = self.rfile.readline()
        if not raw:
            return
        try:
            incoming = WireMessage.from_dict(json.loads(raw.decode("utf-8")))
        except (json.JSONDecodeError, KeyError, TypeError):
            return
        if incoming.payload_type != "job_offer":
            return
        if not incoming.verify_with(self.core_public_key_b64):
            return
        job = incoming.payload.get("job") or {}
        job_id = str(job.get("job_id", ""))
        body = job.get("body") or {}
        allowed = list(job.get("allowed_capabilities") or self.allowed_ops)
        try:
            result = execute_job(body, allowed)
        except Exception as exc:  # noqa: BLE001
            result = {"error": str(exc)}
        out_payload = {
            "job_id": job_id,
            "input_hash": job.get("input_hash") or input_hash(body),
            "result": result,
        }
        reply = new_message(
            sender=self.identity,
            recipient_id=self.core_fingerprint,
            payload_type="job_result",
            payload=out_payload,
        )
        self.wfile.write((json.dumps(reply.to_dict()) + "\n").encode("utf-8"))


def serve_worker(
    *,
    host: str,
    port: int,
    identity: NodeIdentity,
    core_fingerprint: str,
    core_public_key_b64: str,
    allowed_ops: list[str] | None = None,
) -> None:
    ops = allowed_ops or ["compute_sha256"]

    class BoundHandler(WorkerTCPHandler):
        pass

    BoundHandler.identity = identity
    BoundHandler.core_fingerprint = core_fingerprint
    BoundHandler.core_public_key_b64 = core_public_key_b64
    BoundHandler.allowed_ops = ops

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True

    with Server((host, port), BoundHandler) as server:
        server.serve_forever()
