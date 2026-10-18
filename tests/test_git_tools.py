from pathlib import Path
from unittest.mock import MagicMock

import pytest

from privatemind.audit.log import AuditLog
from privatemind.config import Settings
from privatemind.db import Database
from privatemind.improvement.paths import WorkspaceLayout
from privatemind.integrations.git_cli import GitCliResult
from privatemind.tools.git_tools import GitToolHandler
from privatemind.vault.store import AccountKind, CredentialVault


@pytest.fixture
def git_handler(tmp_path: Path) -> tuple[GitToolHandler, CredentialVault, WorkspaceLayout]:
    vault = CredentialVault(tmp_path)
    vault.initialize("pass")
    vault.add_account(
        passphrase="pass",
        name="agent-github",
        kind=AccountKind.GITHUB,
        public={"host": "github.com", "transport": "ssh"},
        secrets={"private_key": "-----BEGIN OPENSSH PRIVATE KEY-----\ntest\n-----END OPENSSH PRIVATE KEY-----\n"},
    )
    vault.unlock("pass")
    layout = WorkspaceLayout(tmp_path)
    db = Database(tmp_path / "mind.sqlite3")
    db.initialize()
    audit = AuditLog(db)
    git = MagicMock()
    handler = GitToolHandler(vault=vault, layout=layout, git=git, audit=audit)
    return handler, vault, layout


def test_git_clone_requires_ssh_url(git_handler: tuple[GitToolHandler, CredentialVault, WorkspaceLayout]) -> None:
    handler, _, _ = git_handler
    bad = handler.invoke("git_clone", {"repo_ssh_url": "https://github.com/x/y.git", "workspace": "w"})
    assert bad.ok is False
    assert "SSH" in bad.detail


def test_git_clone_delegates_to_cli(git_handler: tuple[GitToolHandler, CredentialVault, WorkspaceLayout]) -> None:
    handler, _, layout = git_handler
    handler._git.clone.return_value = GitCliResult(ok=True, stdout="", stderr="", returncode=0)  # noqa: SLF001
    result = handler.invoke(
        "git_clone",
        {
            "repo_ssh_url": "git@github.com:org/repo.git",
            "workspace": "repo",
            "github_account": "agent-github",
        },
    )
    assert result.ok is True
    dest = layout.resolve("repo")
    handler._git.clone.assert_called_once()  # noqa: SLF001
    args = handler._git.clone.call_args[0]  # noqa: SLF001
    assert args[1] == "git@github.com:org/repo.git"
    assert args[2] == dest


def test_git_push_uses_vault_account(git_handler: tuple[GitToolHandler, CredentialVault, WorkspaceLayout]) -> None:
    handler, _, layout = git_handler
    ws = layout.resolve("repo")
    ws.mkdir(parents=True)
    handler._git.current_branch.return_value = GitCliResult(  # noqa: SLF001
        ok=True, stdout="feature\n", stderr="", returncode=0
    )
    handler._git.push.return_value = GitCliResult(ok=True, stdout="", stderr="", returncode=0)  # noqa: SLF001
    result = handler.invoke("git_push", {"workspace": "repo"})
    assert result.ok is True
    handler._git.push.assert_called_once()  # noqa: SLF001
