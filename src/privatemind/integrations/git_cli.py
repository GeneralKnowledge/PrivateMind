import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from privatemind.integrations.ssh_material import git_ssh_command, materialize_ssh_private_key
from privatemind.vault.store import AccountRecord


@dataclass
class GitCliResult:
    ok: bool
    stdout: str
    stderr: str
    returncode: int


class GitCli:
    """Git operations via local CLI with SSH (not GitHub HTTP API)."""

    def __init__(self, runtime_dir: Path) -> None:
        self.runtime_dir = runtime_dir
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

    def _env_for_account(self, account: AccountRecord) -> dict[str, str]:
        key_path = materialize_ssh_private_key(account, self.runtime_dir)
        env = os.environ.copy()
        env["GIT_SSH_COMMAND"] = git_ssh_command(key_path)
        return env

    def probe_ssh(self, account: AccountRecord) -> GitCliResult:
        host = str(account.public.get("host", "github.com"))
        key_path = materialize_ssh_private_key(account, self.runtime_dir)
        cmd = [
            "ssh",
            "-i",
            str(key_path),
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-T",
            f"git@{host}",
        ]
        return self._run(cmd, env={})

    def ls_remote(self, account: AccountRecord, repo_ssh_url: str) -> GitCliResult:
        env = self._env_for_account(account)
        return self._run(["git", "ls-remote", repo_ssh_url], env=env)

    def clone(self, account: AccountRecord, repo_ssh_url: str, dest: Path) -> GitCliResult:
        if dest.exists() and any(dest.iterdir()):
            return GitCliResult(ok=False, stdout="", stderr="destination not empty", returncode=1)
        dest.parent.mkdir(parents=True, exist_ok=True)
        env = self._env_for_account(account)
        return self._run(["git", "clone", repo_ssh_url, str(dest)], env=env)

    def status(self, workdir: Path) -> GitCliResult:
        return self._run(["git", "status", "--short", "--branch"], env=os.environ.copy(), cwd=workdir)

    def checkout_branch(self, workdir: Path, branch: str, *, create: bool = False) -> GitCliResult:
        if create:
            return self._run(["git", "checkout", "-b", branch], env=os.environ.copy(), cwd=workdir)
        return self._run(["git", "checkout", branch], env=os.environ.copy(), cwd=workdir)

    def add(self, workdir: Path, paths: list[str] | None = None) -> GitCliResult:
        cmd = ["git", "add", *(paths or ["."])]
        return self._run(cmd, env=os.environ.copy(), cwd=workdir)

    def commit(self, workdir: Path, message: str) -> GitCliResult:
        return self._run(["git", "commit", "-m", message], env=os.environ.copy(), cwd=workdir)

    def diff(self, workdir: Path, *, staged: bool = False) -> GitCliResult:
        cmd = ["git", "diff"]
        if staged:
            cmd.append("--staged")
        return self._run(cmd, env=os.environ.copy(), cwd=workdir)

    def push(
        self,
        account: AccountRecord,
        workdir: Path,
        *,
        remote: str = "origin",
        branch: str,
        set_upstream: bool = True,
    ) -> GitCliResult:
        env = self._env_for_account(account)
        cmd = ["git", "push"]
        if set_upstream:
            cmd.extend(["-u", remote, branch])
        else:
            cmd.extend([remote, branch])
        return self._run(cmd, env=env, cwd=workdir)

    def current_branch(self, workdir: Path) -> GitCliResult:
        return self._run(["git", "rev-parse", "--abbrev-ref", "HEAD"], env=os.environ.copy(), cwd=workdir)

    @staticmethod
    def _run(cmd: list[str], env: dict[str, str], cwd: Path | None = None) -> GitCliResult:
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                env=env or None,
                cwd=str(cwd) if cwd else None,
                check=False,
            )
        except FileNotFoundError as exc:
            return GitCliResult(ok=False, stdout="", stderr=str(exc), returncode=127)
        except subprocess.TimeoutExpired:
            return GitCliResult(ok=False, stdout="", stderr="timeout", returncode=124)
        ok = proc.returncode == 0
        return GitCliResult(
            ok=ok,
            stdout=proc.stdout,
            stderr=proc.stderr,
            returncode=proc.returncode,
        )
