from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from privatemind.assistance.human import HumanAssistance
from privatemind.executive.tasks import utc_now
from privatemind.improvement.tracker import ImprovementTracker
from privatemind.memory.store import MemoryStore
from privatemind.capabilities.registry import CapabilityRegistry
from pathlib import Path

from privatemind.tools.approved_runner import ApprovedToolRunner
from privatemind.tools.sandbox import SandboxProfile
from privatemind.tools.requests import ToolRequestStore
from privatemind.tools.types import ToolResult
from privatemind.trust import Provenance, TrustLevel

if False:  # TYPE_CHECKING pattern without importing at runtime
    from privatemind.tools.git_tools import GitToolHandler
    from privatemind.improvement.repo_tools import RepoToolHandler
    from privatemind.tools.worker_tools import WorkerToolHandler

FORBIDDEN_REMEMBER_KINDS = frozenset(
    {"system", "improvement_run", "improvement_outcome", "trusted_policy", "human_answer"}
)


class ToolExecutor:
    """Controlled tool execution — only registered tools, fixed privileges."""

    def __init__(
        self,
        memory: MemoryStore,
        assistance: HumanAssistance,
        *,
        git: "GitToolHandler | None" = None,
        repo: "RepoToolHandler | None" = None,
        improvements: ImprovementTracker | None = None,
        tool_requests: ToolRequestStore | None = None,
        auto_approve_tool_requests: bool = False,
        on_tool_approved=None,
        worker: "WorkerToolHandler | None" = None,
        capabilities: CapabilityRegistry | None = None,
        runtime_dir: Path | None = None,
        sandbox_defaults: SandboxProfile | None = None,
    ) -> None:
        self._memory = memory
        self._assistance = assistance
        self._git = git
        self._repo = repo
        self._improvements = improvements or ImprovementTracker(memory)
        self._tool_requests = tool_requests
        self._auto_approve = auto_approve_tool_requests
        self._on_tool_approved = on_tool_approved
        self._worker = worker
        self._capabilities = capabilities
        rt = runtime_dir or Path.home() / ".privatemind" / "runtime"
        self._approved_runner = ApprovedToolRunner(runtime_dir=rt, default_profile=sandbox_defaults)
        self._allowed = {
            "remember": self._remember,
            "recall": self._recall,
            "compute_sha256": self._compute_sha256,
            "request_human_help": self._request_human_help,
            "record_limitation": self._record_limitation,
            "request_tool": self._request_tool,
        }

    def list_tools(self) -> list[str]:
        names = list(self._allowed.keys())
        if self._git:
            names.extend(self._git.tool_names())
        if self._repo:
            names.extend(self._repo.tool_names())
        if self._worker:
            names.extend(self._worker.tool_names())
        return sorted(set(names))

    def invoke(self, name: str, arguments: dict[str, Any], *, task_id: str | None = None) -> ToolResult:
        if self._worker and name in self._worker.tool_names():
            return self._worker.invoke(name, arguments, task_id=task_id)
        if self._repo and name in self._repo.tool_names():
            return self._repo.invoke(name, arguments)
        if self._git and name in self._git.tool_names():
            return self._git.invoke(name, arguments, task_id=task_id)
        if self._capabilities:
            approved_caps = [
                c
                for c in self._capabilities.find_for_operation(name)
                if c.kind == "tool" and c.id.startswith("tool.requested.")
            ]
            if approved_caps:
                return self._approved_runner.invoke(approved_caps[0], name, arguments, task_id=task_id)
        if name not in self._allowed:
            return ToolResult(ok=False, output=None, detail=f"Tool not allowed: {name}")
        try:
            return self._allowed[name](arguments, task_id=task_id)
        except Exception as exc:  # noqa: BLE001 — tool boundary
            return ToolResult(ok=False, output=None, detail=str(exc))

    def _remember(self, arguments: dict[str, Any], task_id: str | None = None) -> ToolResult:
        kind = str(arguments.get("kind", "fact"))
        if kind in FORBIDDEN_REMEMBER_KINDS:
            return ToolResult(
                ok=False,
                output=None,
                detail=f"remember kind '{kind}' requires trusted-core promotion",
            )
        key = str(arguments["key"])
        content = str(arguments["content"])
        provenance = Provenance.TOOL_OUTPUT
        trust = TrustLevel.UNVERIFIED
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

    def _record_limitation(self, arguments: dict[str, Any], task_id: str | None = None) -> ToolResult:
        key = str(arguments["key"])
        self._improvements.record_limitation(
            key=key,
            summary=str(arguments.get("summary", "")),
            evidence=str(arguments.get("evidence", "")),
            severity=str(arguments.get("severity", "medium")),
            component=str(arguments.get("component", "unknown")),
            status=str(arguments.get("status", "open")),
        )
        return ToolResult(ok=True, output={"recorded": True, "key": key})

    def _request_tool(self, arguments: dict[str, Any], task_id: str | None = None) -> ToolResult:
        if not self._tool_requests:
            return ToolResult(ok=False, output=None, detail="Tool request store not configured")
        tool_name = str(arguments["tool_name"])
        purpose = str(arguments.get("purpose", ""))
        justification = str(arguments.get("justification", ""))
        risk_notes = str(arguments.get("risk_notes", ""))
        req_id = self._tool_requests.create(
            tool_name=tool_name,
            purpose=purpose,
            justification=justification,
            risk_notes=risk_notes,
            task_id=task_id,
        )
        status = "pending"
        if self._auto_approve and self._on_tool_approved:
            cap_id = self._on_tool_approved(req_id, tool_name, purpose, justification)
            if cap_id:
                status = "auto_approved"
        return ToolResult(
            ok=True,
            output={"request_id": req_id, "status": status, "tool_name": tool_name},
            detail="Operator grants tools on the dedicated server; see privatemind tool-request list",
        )

    def _request_human_help(self, arguments: dict[str, Any], task_id: str | None = None) -> ToolResult:
        question = str(arguments["question"])
        context = arguments.get("context", {})
        req_id = self._assistance.create_request(question, context=context, task_id=task_id)
        return ToolResult(
            ok=True,
            output={"request_id": req_id, "status": "pending"},
            detail="Human assistance requested; task should block until answered.",
        )
