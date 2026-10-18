import json
import subprocess
from typing import Any

from privatemind.capabilities.registry import Capability
from privatemind.tools.types import ToolResult


class ApprovedToolRunner:
    """Run operator-approved tools in a subprocess (fixed argv, no shell)."""

    def __init__(self, *, default_timeout_seconds: int = 120) -> None:
        self._timeout = default_timeout_seconds

    def invoke(
        self,
        capability: Capability,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        task_id: str | None = None,
    ) -> ToolResult:
        argv = capability.limits.get("runner_argv")
        if not isinstance(argv, list) or not argv:
            return ToolResult(
                ok=False,
                output=None,
                detail=(
                    f"Tool '{tool_name}' is approved (capability {capability.id}) "
                    "but has no runner_argv configured. "
                    "Re-approve with: privatemind tool-request approve ... --runner-arg ..."
                ),
            )
        cmd = [str(part) for part in argv]
        payload = json.dumps({"tool": tool_name, "arguments": arguments, "task_id": task_id})
        try:
            proc = subprocess.run(
                cmd,
                input=payload,
                capture_output=True,
                text=True,
                timeout=int(capability.limits.get("timeout_seconds") or self._timeout),
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(ok=False, output=None, detail="approved tool runner timed out")
        except OSError as exc:
            return ToolResult(ok=False, output=None, detail=str(exc))

        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()
        if proc.returncode != 0:
            return ToolResult(
                ok=False,
                output={"stdout": stdout[:8000], "stderr": stderr[:2000], "returncode": proc.returncode},
                detail=f"approved tool exited {proc.returncode}",
            )
        try:
            parsed = json.loads(stdout) if stdout else {}
        except json.JSONDecodeError:
            parsed = {"stdout": stdout[:8000]}
        return ToolResult(ok=True, output=parsed, detail=f"ran via {capability.id}")
