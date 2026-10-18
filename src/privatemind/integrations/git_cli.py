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
        key_path = materialize_ssh_private_key(account, self.runtime_dir)
        env = os.environ.copy()
        env["GIT_SSH_COMMAND"] = git_ssh_command(key_path)
        return self._run(["git", "ls-remote", repo_ssh_url], env=env)

    @staticmethod
    def _run(cmd: list[str], env: dict[str, str]) -> GitCliResult:
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                env=env or None,
                check=False,
            )
        except FileNotFoundError as exc:
            return GitCliResult(ok=False, stdout="", stderr=str(exc), returncode=127)
        except subprocess.TimeoutExpired:
            return GitCliResult(ok=False, stdout="", stderr="timeout", returncode=124)
        ok = proc.returncode in (0, 1)
        return GitCliResult(
            ok=ok,
            stdout=proc.stdout,
            stderr=proc.stderr,
            returncode=proc.returncode,
        )
