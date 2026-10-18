import json
import uuid
from typing import Any

from privatemind.audit.log import AuditLog
from privatemind.memory.store import MemoryStore
from privatemind.trust import Provenance, TrustLevel
from privatemind.worker.contract import JobPackage, JobPayloadType
from privatemind.worker.envelope import WireMessage, new_message
from privatemind.worker.identity import NodeIdentity
from privatemind.worker.pairing_store import PairingStore
from privatemind.worker.transport import WorkerTransportError, send_message
from privatemind.worker.verifier import build_verification_record, input_hash, record_to_dict


class WorkerHub:
    def __init__(
        self,
        *,
        core_identity: NodeIdentity,
        pairing: PairingStore,
        memory: MemoryStore,
        audit: AuditLog,
        host: str = "127.0.0.1",
        port: int = 8765,
    ) -> None:
        self.core = core_identity
        self.pairing = pairing
        self.memory = memory
        self.audit = audit
        self.host = host
        self.port = port

    def delegate_compute_sha256(
        self,
        text: str,
        *,
        worker_fingerprint: str,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        return self.delegate_operation(
            worker_fingerprint=worker_fingerprint,
            operation="compute_sha256",
            body={"op": "compute_sha256", "text": text},
            task_id=task_id,
        )

    def delegate_operation(
        self,
        *,
        worker_fingerprint: str,
        operation: str,
        body: dict[str, Any],
        task_id: str | None = None,
    ) -> dict[str, Any]:
        peer = self.pairing.get_peer(worker_fingerprint)
        if not peer or peer.get("trust_state") != "paired":
            return {"ok": False, "error": "worker not paired or revoked"}

        lease = self.pairing.active_lease(worker_fingerprint, operation)
        if not lease:
            return {"ok": False, "error": "no active lease for operation"}

        job_id = str(uuid.uuid4())
        ih = input_hash(body)
        package = JobPackage(
            job_id=job_id,
            payload_type=JobPayloadType.COMPUTE,
            input_hash=ih,
            body=body,
            allowed_capabilities=[operation],
        )
        job_dict = {
            "job_id": package.job_id,
            "payload_type": package.payload_type.value,
            "input_hash": package.input_hash,
            "body": package.body,
            "allowed_capabilities": package.allowed_capabilities,
        }
        offer = new_message(
            sender=self.core,
            recipient_id=worker_fingerprint,
            payload_type="job_offer",
            payload={"job": job_dict},
        )

        try:
            raw = send_message(self.host, self.port, offer.to_dict())
        except WorkerTransportError as exc:
            self.audit.record("worker_delegate_failed", job_id=job_id, error=str(exc))
            return {"ok": False, "error": str(exc), "job_id": job_id}

        response = WireMessage.from_dict(raw)
        if not self.pairing.record_replay(response.msg_id):
            return {"ok": False, "error": "replay detected", "job_id": job_id}

        auth_ok = response.verify_with(peer["public_key_b64"])
        payload = response.payload or {}
        result = payload.get("result") or {}

        verification = build_verification_record(
            job_id=job_id,
            authenticity_ok=auth_ok,
            operation=operation,
            body=body,
            result=result,
        )
        self.audit.record(
            "worker_verification",
            job_id=job_id,
            authenticity=verification.authenticity_ok,
            correctness=verification.correctness_status,
            accepted=verification.accepted,
        )
        self.memory.upsert(
            kind="worker_result",
            key=job_id,
            content=json.dumps(
                {
                    "result": result,
                    "verification": record_to_dict(verification),
                }
            ),
            provenance=Provenance.WORKER_RESPONSE,
            trust_level=TrustLevel.UNVERIFIED
            if not verification.accepted
            else TrustLevel.PARTIALLY_VERIFIED,
            metadata={"task_id": task_id, "worker": worker_fingerprint},
        )

        return {
            "ok": verification.accepted,
            "job_id": job_id,
            "result": result,
            "verification": record_to_dict(verification),
        }
