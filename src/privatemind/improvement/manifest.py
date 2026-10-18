import json
from enum import Enum
from typing import Any

from privatemind.memory.store import MemoryStore
from privatemind.trust import Provenance, TrustLevel


class ImprovementPhase(str, Enum):
    INIT = "init"
    DISCOVER = "discover"
    INVESTIGATE = "investigate"
    IMPLEMENT = "implement"
    VERIFY = "verify"
    SUBMIT = "submit"
    RECORD = "record"
    DONE = "done"
    FAILED = "failed"


class ImprovementManifest:
    def __init__(self, memory: MemoryStore, task_id: str) -> None:
        self._memory = memory
        self._task_id = task_id
        self._key = f"manifest.{task_id}"

    def load(self) -> dict[str, Any]:
        row = self._memory.get("improvement_run", self._key)
        if not row:
            return {
                "phase": ImprovementPhase.INIT.value,
                "checkpoints": {},
                "tests_passed": False,
                "verify_passed": False,
                "push_done": False,
                "security_review_required": False,
            }
        return json.loads(row["content"])

    def save(self, data: dict[str, Any]) -> None:
        self._memory.upsert(
            kind="improvement_run",
            key=self._key,
            content=json.dumps(data),
            provenance=Provenance.TRUSTED_CORE,
            trust_level=TrustLevel.VERIFIED,
            metadata={"task_id": self._task_id},
        )

    def set_phase(self, phase: ImprovementPhase) -> dict[str, Any]:
        data = self.load()
        data["phase"] = phase.value
        self.save(data)
        return data

    def checkpoint(self, name: str, value: Any = True) -> dict[str, Any]:
        data = self.load()
        checkpoints = data.setdefault("checkpoints", {})
        checkpoints[name] = value
        self.save(data)
        return data

    def has_checkpoint(self, name: str) -> bool:
        return bool(self.load().get("checkpoints", {}).get(name))
