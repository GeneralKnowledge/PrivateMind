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
from privatemind.worker.mtls import MtlsPaths, build_client_ssl_context
from privatemind.worker.transport import WorkerTransportError, send_message
import ssl
from privatemind.worker.trust import auto_accept_results, can_delegate
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
        mtls_paths: MtlsPaths | None = None,
        default_use_mtls: bool = False,
        quarantine_failure_threshold: int = 3,
    ) -> None:
        self.core = core_identity
        self.pairing = pairing
        self.memory = memory
        self.audit = audit
        self.host = host
        self.port = port
        self._mtls_paths = mtls_paths
        self._default_use_mtls = default_use_mtls
        self._quarantine_failure_threshold = quarantine_failure_threshold
        self._client_ssl: ssl.SSLContext | None = None
        if mtls_paths and mtls_paths.ca_cert.is_file():
            self._client_ssl = build_client_ssl_context(mtls_paths)

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
        if not peer:
            return {"ok": False, "error": "worker not paired or revoked"}
        trust_state = str(peer.get("trust_state") or "")
        if not can_delegate(trust_state):
            if trust_state == "quarantined":
                return {"ok": False, "error": "worker quarantined"}
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

        host = str(peer.get("endpoint_host") or self.host)
        port = int(peer.get("endpoint_port") or self.port)
        use_mtls = bool(peer.get("use_mtls")) if peer.get("use_mtls") is not None else self._default_use_mtls
        ssl_ctx = self._client_ssl if use_mtls else None
        if use_mtls and ssl_ctx is None:
            return {"ok": False, "error": "mTLS required but core PKI not configured", "job_id": job_id}

        try:
            raw = send_message(host, port, offer.to_dict(), ssl_context=ssl_ctx)
        except WorkerTransportError as exc:
            self.audit.record("worker_delegate_failed", job_id=job_id, error=str(exc))
            return {"ok": False, "error": str(exc), "job_id": job_id}

        response = WireMessage.from_dict(raw)
        if not self.pairing.record_replay(response.msg_id):
            return {"ok": False, "error": "replay detected", "job_id": job_id}

        auth_ok = response.verify_with(peer["public_key_b64"])
        payload = response.payload or {}
        result = payload.get("result") if isinstance(payload.get("result"), dict) else {}

        verification = build_verification_record(
            job_id=job_id,
            expected_input_hash=ih,
            authenticity_ok=auth_ok,
            operation=operation,
            body=body,
            response_payload=payload,
            allow_accept=auto_accept_results(trust_state),
        )
        outcome = self.pairing.record_verification_outcome(
            worker_fingerprint=worker_fingerprint,
            job_id=job_id,
            accepted=verification.accepted,
            authenticity_ok=verification.authenticity_ok,
            correctness_status=verification.correctness_status,
            failure_threshold=self._quarantine_failure_threshold,
        )
        if outcome.get("quarantined"):
            self.audit.record(
                "worker_auto_quarantined",
                worker=worker_fingerprint,
                job_id=job_id,
                threshold=self._quarantine_failure_threshold,
            )
        self.audit.record(
            "worker_verification",
            job_id=job_id,
            authenticity=verification.authenticity_ok,
            correctness=verification.correctness_status,
            accepted=verification.accepted,
            trust_state=trust_state,
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
