import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any

from privatemind.assistance.human import HumanAssistance
from privatemind.executive.tasks import utc_now
from privatemind.memory.store import MemoryStore
from privatemind.trust import Provenance, TrustLevel


@dataclass
class ToolResult:
    ok: bool
    output: Any
    detail: str = ""


class ToolExecutor:
    """Controlled tool execution — only registered tools, fixed privileges."""

    def __init__(self, memory: MemoryStore, assistance: HumanAssistance) -> None:
        self._memory = memory
        self._assistance = assistance
        self._allowed = {
            "remember": self._remember,
            "recall": self._recall,
            "compute_sha256": self._compute_sha256,
            "request_human_help": self._request_human_help,
        }

    def list_tools(self) -> list[str]:
        return sorted(self._allowed.keys())

    def invoke(self, name: str, arguments: dict[str, Any], *, task_id: str | None = None) -> ToolResult:
        if name not in self._allowed:
            return ToolResult(ok=False, output=None, detail=f"Tool not allowed: {name}")
        try:
            return self._allowed[name](arguments, task_id=task_id)
        except Exception as exc:  # noqa: BLE001 — tool boundary
            return ToolResult(ok=False, output=None, detail=str(exc))

    def _remember(self, arguments: dict[str, Any], task_id: str | None = None) -> ToolResult:
        kind = str(arguments.get("kind", "fact"))
        key = str(arguments["key"])
        content = str(arguments["content"])
        provenance = Provenance.TRUSTED_CORE
        trust = TrustLevel.VERIFIED
        self._memory.upsert(
            kind=kind,
            key=key,
            content=content,
            provenance=provenance,
            trust_level=trust,
            metadata={"task_id": task_id},
        )
        return ToolResult(ok=True, output={"stored": True, "kind": kind, "key": key})

    def _recall(self, arguments: dict[str, Any], task_id: str | None = None) -> ToolResult:
        kind = str(arguments.get("kind", "fact"))
        key = str(arguments["key"])
        entry = self._memory.get(kind, key)
        if not entry:
            return ToolResult(ok=True, output=None, detail="not_found")
        return ToolResult(ok=True, output=entry)

    def _compute_sha256(self, arguments: dict[str, Any], task_id: str | None = None) -> ToolResult:
        text = str(arguments.get("text", ""))
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return ToolResult(ok=True, output={"sha256": digest, "input_length": len(text)})

    def _request_human_help(self, arguments: dict[str, Any], task_id: str | None = None) -> ToolResult:
        question = str(arguments["question"])
        context = arguments.get("context", {})
        req_id = self._assistance.create_request(question, context=context, task_id=task_id)
        return ToolResult(
            ok=True,
            output={"request_id": req_id, "status": "pending"},
            detail="Human assistance requested; task should block until answered.",
        )
