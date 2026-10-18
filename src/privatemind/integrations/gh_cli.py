import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GhResult:
    ok: bool
    stdout: str
    stderr: str
    returncode: int

    @property
    def pr_url(self) -> str | None:
        text = (self.stdout or self.stderr).strip()
        for line in text.splitlines():
            if line.startswith("http") and "pull" in line:
                return line.strip()
        return None


def gh_available() -> bool:
    return shutil.which("gh") is not None


def create_draft_pull_request(
    *,
    workspace: Path,
    branch: str,
    title: str,
    body: str,
    base: str = "main",
) -> GhResult:
    if not gh_available():
        return GhResult(ok=False, stdout="", stderr="gh CLI not found", returncode=127)
    cmd = [
        "gh",
        "pr",
        "create",
        "--draft",
        "--base",
        base,
        "--head",
        branch,
        "--title",
        title,
        "--body",
        body,
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return GhResult(ok=proc.returncode == 0, stdout=proc.stdout, stderr=proc.stderr, returncode=proc.returncode)


def format_improvement_pr_body(*, task_id: str, workspace: str, tests_passed: bool) -> str:
    return (
        "## PrivateMind self-improvement (draft)\n\n"
        f"- Task: `{task_id}`\n"
        f"- Workspace: `{workspace}`\n"
        f"- Tests passed in trusted workflow: **{tests_passed}**\n\n"
        "Merge only after human review. The trusted core does not auto-merge to main.\n"
    )
