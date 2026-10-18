import os
import stat
from pathlib import Path

from privatemind.vault.store import AccountRecord


def materialize_ssh_private_key(account: AccountRecord, runtime_dir: Path) -> Path:
    """
    Write SSH private key from vault to a restricted path for git/ssh CLI use.
    Prefer this over embedding keys in URLs or using HTTPS tokens for GitHub.
    """
    key_pem = account.secrets.get("private_key")
    if not key_pem:
        raise ValueError(f"Account {account.name} has no private_key secret")

    keys_dir = runtime_dir / "ssh"
    keys_dir.mkdir(parents=True, exist_ok=True)
    key_path = keys_dir / f"{account.id}.key"
    key_path.write_text(key_pem.strip() + "\n", encoding="utf-8")
    key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return key_path


def git_ssh_command(key_path: Path, *, host: str = "github.com") -> str:
    identity = str(key_path)
    return (
        f"ssh -i {identity} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new "
        f"-o UserKnownHostsFile={key_path.parent / f'known_hosts_{host}'}"
    )


def ssh_target_command(account: AccountRecord, key_path: Path) -> list[str]:
    host = str(account.public.get("host", ""))
    user = str(account.public.get("user", "root"))
    port = int(account.public.get("port", 22))
    return [
        "ssh",
        "-i",
        str(key_path),
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "BatchMode=yes",
        "-p",
        str(port),
        f"{user}@{host}",
    ]
