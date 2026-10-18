"""
Worker network contract (not yet networked).

Grounded in current executive/memory patterns:
- Job packages are opaque to workers beyond scoped payload.
- Responses are authenticated separately from correctness validation.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class JobPayloadType(str, Enum):
    COMPUTE = "compute"
    RESEARCH = "research"
    CODE = "code"


@dataclass
class JobPackage:
    job_id: str
    payload_type: JobPayloadType
    input_hash: str
    body: dict[str, Any]
    allowed_capabilities: list[str]


@dataclass
class JobResponseEnvelope:
    job_id: str
    worker_id: str
    payload: dict[str, Any]
    signature: str
    sent_at: str


@dataclass
class VerificationRecord:
    job_id: str
    authenticity_ok: bool
    correctness_status: str  # pending | passed | failed
    accepted: bool
