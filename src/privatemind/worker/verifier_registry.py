from collections.abc import Callable
from typing import Any

from privatemind.worker.verifier import verify_compute_sha256

VerifierFn = Callable[[dict[str, Any], dict[str, Any]], bool]

_REGISTRY: dict[str, VerifierFn] = {
    "compute_sha256": verify_compute_sha256,
}


def register_verifier(operation: str, fn: VerifierFn) -> None:
    _REGISTRY[operation] = fn


def verify_operation(operation: str, body: dict[str, Any], result: dict[str, Any]) -> bool:
    fn = _REGISTRY.get(operation)
    if fn is None:
        return False
    return fn(body, result)


def registered_operations() -> list[str]:
    return sorted(_REGISTRY.keys())
