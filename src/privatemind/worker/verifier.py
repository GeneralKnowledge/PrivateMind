import hashlib
import json
from dataclasses import asdict
from typing import Any

from privatemind.worker.contract import VerificationRecord


def input_hash(body: dict[str, Any]) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_compute_sha256(body: dict[str, Any], result: dict[str, Any]) -> bool:
    if "error" in result:
        return False
    text = str(body.get("text", ""))
    expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return str(result.get("sha256", "")) == expected


def verify_correctness(operation: str, body: dict[str, Any], result: dict[str, Any]) -> bool:
    if operation == "compute_sha256":
        return verify_compute_sha256(body, result)
    return False


def validate_job_result_payload(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(payload, dict):
        return False, ["payload_not_object"]
    if not str(payload.get("job_id", "")).strip():
        reasons.append("missing_job_id")
    ih = payload.get("input_hash")
    if not isinstance(ih, str) or len(ih) != 64:
        reasons.append("invalid_input_hash")
    result = payload.get("result")
    if not isinstance(result, dict):
        reasons.append("result_not_object")
    return len(reasons) == 0, reasons


def build_verification_record(
    *,
    job_id: str,
    expected_input_hash: str,
    authenticity_ok: bool,
    operation: str,
    body: dict[str, Any],
    response_payload: dict[str, Any],
    allow_accept: bool = True,
) -> VerificationRecord:
    reasons: list[str] = []
    schema_ok, schema_reasons = validate_job_result_payload(response_payload)
    reasons.extend(schema_reasons)

    result = response_payload.get("result") if isinstance(response_payload.get("result"), dict) else {}
    if str(response_payload.get("job_id", "")) != job_id:
        reasons.append("job_id_mismatch")
        job_id_ok = False
    else:
        job_id_ok = True

    reported_hash = str(response_payload.get("input_hash", ""))
    input_hash_ok = reported_hash == expected_input_hash
    if not input_hash_ok:
        reasons.append("input_hash_mismatch")

    if not authenticity_ok:
        reasons.append("authenticity_failed")

    correctness = (
        verify_correctness(operation, body, result)
        if authenticity_ok and schema_ok and job_id_ok and input_hash_ok
        else False
    )
    status = "passed" if correctness else "failed"
    if not authenticity_ok:
        status = "failed"

    accepted = (
        allow_accept
        and authenticity_ok
        and schema_ok
        and job_id_ok
        and input_hash_ok
        and correctness
    )
    return VerificationRecord(
        job_id=job_id,
        authenticity_ok=authenticity_ok,
        schema_ok=schema_ok and job_id_ok,
        input_hash_ok=input_hash_ok,
        correctness_status=status,
        accepted=accepted,
        rejection_reasons=reasons,
    )


def record_to_dict(record: VerificationRecord) -> dict[str, Any]:
    return asdict(record)
