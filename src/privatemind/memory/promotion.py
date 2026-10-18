from privatemind.memory.store import MemoryStore
from privatemind.trust import Provenance, TrustLevel

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    TrustLevel.UNVERIFIED.value: {TrustLevel.PARTIALLY_VERIFIED.value, TrustLevel.REJECTED.value},
    TrustLevel.PARTIALLY_VERIFIED.value: {TrustLevel.VERIFIED.value, TrustLevel.REJECTED.value},
    TrustLevel.VERIFIED.value: {TrustLevel.REJECTED.value},
    TrustLevel.REJECTED.value: set(),
}


def promote_memory_trust(
    memory: MemoryStore,
    *,
    kind: str,
    key: str,
    target_level: TrustLevel,
    evidence: str,
    actor: str = "operator",
) -> dict:
    entry = memory.get(kind, key)
    if not entry:
        return {"ok": False, "error": "memory entry not found"}
    current = str(entry.get("trust_level") or TrustLevel.UNVERIFIED.value)
    target = target_level.value
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        return {"ok": False, "error": f"transition {current} -> {target} not allowed"}
    provenance = Provenance.HUMAN_VERIFIED if target == TrustLevel.VERIFIED.value else Provenance.TRUSTED_CORE
    memory.upsert(
        kind=kind,
        key=key,
        content=str(entry.get("content") or ""),
        provenance=provenance,
        trust_level=TrustLevel(target),
        metadata={
            "promotion_evidence": evidence[:4000],
            "promotion_actor": actor,
            "previous_trust_level": current,
        },
    )
    return {"ok": True, "kind": kind, "key": key, "trust_level": target}
