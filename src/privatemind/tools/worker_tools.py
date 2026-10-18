from typing import Any

from privatemind.tools.types import ToolResult
from privatemind.worker.hub import WorkerHub


class WorkerToolHandler:
    def __init__(self, hub: WorkerHub | None) -> None:
        self._hub = hub

    def tool_names(self) -> list[str]:
        return ["worker_delegate"]

    def invoke(self, name: str, arguments: dict[str, Any], *, task_id: str | None = None) -> ToolResult:
        if name != "worker_delegate" or not self._hub:
            return ToolResult(ok=False, output=None, detail="Worker hub not configured")
        op = str(arguments.get("operation", "compute_sha256"))
        worker_fp = str(arguments["worker_fingerprint"])
        body = dict(arguments.get("body") or {})
        if op == "compute_sha256" and "text" in arguments:
            body = {"op": "compute_sha256", "text": str(arguments["text"])}
        if not body:
            body = {"op": op}
        out = self._hub.delegate_operation(
            worker_fingerprint=worker_fp,
            operation=op,
            body=body,
            task_id=task_id,
        )
        return ToolResult(ok=bool(out.get("ok")), output=out, detail="" if out.get("ok") else str(out.get("error")))
