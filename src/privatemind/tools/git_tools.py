import shlex
import subprocess
from pathlib import Path
from typing import Any

from privatemind.audit.log import AuditLog
from privatemind.improvement.paths import WorkspaceLayout
from privatemind.integrations.git_cli import GitCli, GitCliResult
from privatemind.security.policy import find_sensitive_paths, normalize_repo_path
from privatemind.security.protected_manifest import find_protected_paths
from privatemind.tools.types import ToolResult
from privatemind.vault.store import CredentialVault


def _as_output(result: GitCliResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


class GitToolHandler:
    """Allowlisted git/ssh tools using vault GitHub identity (CLI only)."""

    DEFAULT_GITHUB_ACCOUNT = "agent-github"

    def __init__(
        self,
        *,
        vault: CredentialVault,
        layout: WorkspaceLayout,
        git: GitCli,
        audit: AuditLog,
    ) -> None:
        self._vault = vault
        self._layout = layout
        self._git = git
        self._audit = audit
        self._handlers = {
            "git_clone": self._git_clone,
            "git_status": self._git_status,
            "git_branch": self._git_branch,
            "git_diff": self._git_diff,
            "git_commit": self._git_commit,
            "git_push": self._git_push,
            "run_tests": self._run_tests,
        }

    def tool_names(self) -> list[str]:
        return sorted(self._handlers.keys())

    def invoke(self, name: str, arguments: dict[str, Any], *, task_id: str | None = None) -> ToolResult:
        if name not in self._handlers:
            return ToolResult(ok=False, output=None, detail=f"Unknown git tool: {name}")
        if not self._vault.is_unlocked():
            return ToolResult(ok=False, output=None, detail="Vault locked; cannot use git tools")
        try:
            result = self._handlers[name](arguments)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(ok=False, output=None, detail=str(exc))
        self._audit.record("git_tool", tool=name, task_id=task_id, ok=result.ok, detail=result.detail)
        return result

    def _workdir(self, arguments: dict[str, Any]) -> Path:
        name = str(arguments["workspace"])
        path = self._layout.resolve(name)
        if not path.is_dir():
            raise FileNotFoundError(f"Workspace not found: {name}")
        return path

    def _github_account(self, arguments: dict[str, Any]):
        account_name = str(arguments.get("github_account", self.DEFAULT_GITHUB_ACCOUNT))
        acct = self._vault.get_by_name(account_name)
        if not acct or not acct.enabled:
            raise ValueError(f"GitHub account not found or disabled: {account_name}")
        return acct

    def _git_clone(self, arguments: dict[str, Any]) -> ToolResult:
        repo_ssh_url = str(arguments["repo_ssh_url"])
        if not repo_ssh_url.startswith("git@"):
            return ToolResult(ok=False, output=None, detail="Only SSH clone URLs (git@...) are allowed")
        workspace = str(arguments["workspace"])
        dest = self._layout.resolve(workspace)
        if dest.exists() and (dest / ".git").is_dir():
            return ToolResult(ok=True, output={"skipped": True, "reason": "already_cloned"})
        account = self._github_account(arguments)
        result = self._git.clone(account, repo_ssh_url, dest)
        return ToolResult(ok=result.ok, output=_as_output(result), detail=result.stderr if not result.ok else "")

    def _git_status(self, arguments: dict[str, Any]) -> ToolResult:
        result = self._git.status(self._workdir(arguments))
        return ToolResult(ok=result.ok, output=_as_output(result))

    def _git_branch(self, arguments: dict[str, Any]) -> ToolResult:
        branch = str(arguments["branch"])
        create = bool(arguments.get("create", True))
        result = self._git.checkout_branch(self._workdir(arguments), branch, create=create)
        return ToolResult(ok=result.ok, output=_as_output(result), detail=result.stderr if not result.ok else "")

    def _git_diff(self, arguments: dict[str, Any]) -> ToolResult:
        staged = bool(arguments.get("staged", False))
        result = self._git.diff(self._workdir(arguments), staged=staged)
        return ToolResult(ok=result.ok, output=_as_output(result))

    def _git_commit(self, arguments: dict[str, Any]) -> ToolResult:
        workdir = self._workdir(arguments)
        message = str(arguments["message"])
        paths = arguments.get("paths")
        if paths is not None:
            add_paths = [normalize_repo_path(str(p)) for p in paths]
            blocked = sorted(set(find_sensitive_paths(add_paths) + find_protected_paths(add_paths)))
            if blocked:
                return ToolResult(
                    ok=False,
                    output={"blocked_paths": blocked},
                    detail="security_review_required: sensitive paths in commit",
                )
            add_result = self._git.add(workdir, add_paths)
            if not add_result.ok:
                return ToolResult(ok=False, output=_as_output(add_result), detail=add_result.stderr)
        else:
            add_result = self._git.add(workdir, None)
            if not add_result.ok:
                return ToolResult(ok=False, output=_as_output(add_result), detail=add_result.stderr)
        result = self._git.commit(workdir, message)
        return ToolResult(ok=result.ok, output=_as_output(result), detail=result.stderr if not result.ok else "")

    def _git_push(self, arguments: dict[str, Any]) -> ToolResult:
        workdir = self._workdir(arguments)
        branch = arguments.get("branch")
        if not branch:
            cur = self._git.current_branch(workdir)
            if not cur.ok:
                return ToolResult(ok=False, output=_as_output(cur), detail=cur.stderr)
            branch = cur.stdout.strip()
        account = self._github_account(arguments)
        result = self._git.push(account, workdir, branch=str(branch))
        return ToolResult(ok=result.ok, output=_as_output(result), detail=result.stderr if not result.ok else "")

    def _run_tests(self, arguments: dict[str, Any]) -> ToolResult:
        workdir = self._workdir(arguments)
        cmd = str(arguments.get("command", "python3 -m pytest -q"))
        parts = shlex.split(cmd)
        proc = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(workdir),
            check=False,
        )
        output = {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
        return ToolResult(ok=proc.returncode == 0, output=output, detail=proc.stderr if proc.returncode else "")
