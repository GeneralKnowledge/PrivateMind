"""Trust boundaries: provenance and acceptance of information."""

from enum import Enum


class Provenance(str, Enum):
    """Where a piece of knowledge originated."""

    TRUSTED_CORE = "trusted_core"
    MODEL_INFERENCE = "model_inference"
    TOOL_OUTPUT = "tool_output"
    EXTERNAL_UNTRUSTED = "external_untrusted"
    HUMAN_VERIFIED = "human_verified"
    WORKER_RESPONSE = "worker_response"


class TrustLevel(str, Enum):
    UNVERIFIED = "unverified"
    PARTIALLY_VERIFIED = "partially_verified"
    VERIFIED = "verified"
    REJECTED = "rejected"


# External channels must never be treated as instruction sources with inherent authority.
UNTRUSTED_PROVENANCE = frozenset(
    {
        Provenance.EXTERNAL_UNTRUSTED,
        Provenance.WORKER_RESPONSE,
        Provenance.TOOL_OUTPUT,
        Provenance.MODEL_INFERENCE,
    }
)
