import json
import subprocess
from pathlib import Path
from typing import Any

from privatemind.capabilities.registry import Capability
from privatemind.tools.sandbox import SandboxProfile, run_sandboxed
from privatemind.tools.types import ToolResult


class ApprovedToolRunner:
    """Run operator-approved tools in a sandboxed subprocess (fixed argv, no shell)."""

    def __init__(
        self,
        *,
        runtime_dir: Path,
        default_profile: SandboxProfile | None = None,
    ) -> None:
        self._runtime_dir = runtime_dir / "tool_sandbox"
        self._default_profile = default_profile or SandboxProfile()

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
        profile = SandboxProfile.from_capability_limits(capability.limits, defaults=self._default_profile)
        try:
            result = run_sandboxed(
                cmd,
                stdin_text=payload,
                profile=profile,
                runtime_root=self._runtime_dir,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(ok=False, output=None, detail="approved tool runner timed out")
        except OSError as exc:
            return ToolResult(ok=False, output=None, detail=str(exc))

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        if result.returncode != 0:
            return ToolResult(
                ok=False,
                output={
                    "stdout": stdout[:8000],
                    "stderr": stderr[:2000],
                    "returncode": result.returncode,
                    "sandbox_wrapper": result.wrapper,
                },
                detail=f"approved tool exited {result.returncode}",
            )
        try:
            parsed = json.loads(stdout) if stdout else {}
        except json.JSONDecodeError:
            parsed = {"stdout": stdout[:8000]}
        if isinstance(parsed, dict):
            parsed.setdefault("_sandbox", {"wrapper": result.wrapper})
        return ToolResult(ok=True, output=parsed, detail=f"ran via {capability.id} (sandboxed)")
