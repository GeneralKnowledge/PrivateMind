import hashlib
import json
from dataclasses import asdict
from typing import Any

from privatemind.worker.contract import VerificationRecord


def input_hash(body: dict[str, Any]) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_compute_sha256(body: dict[str, Any], result: dict[str, Any]) -> bool:
    text = str(body.get("text", ""))
    expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return str(result.get("sha256", "")) == expected


def verify_correctness(operation: str, body: dict[str, Any], result: dict[str, Any]) -> bool:
    if operation == "compute_sha256":
        return verify_compute_sha256(body, result)
    return False


def build_verification_record(
    *,
    job_id: str,
    authenticity_ok: bool,
    operation: str,
    body: dict[str, Any],
    result: dict[str, Any],
) -> VerificationRecord:
    correctness = verify_correctness(operation, body, result) if authenticity_ok else False
    accepted = authenticity_ok and correctness
    status = "passed" if correctness else "failed"
    if not authenticity_ok:
        status = "failed"
    return VerificationRecord(
        job_id=job_id,
        authenticity_ok=authenticity_ok,
        correctness_status=status,
        accepted=accepted,
    )


def record_to_dict(record: VerificationRecord) -> dict[str, Any]:
    return asdict(record)
