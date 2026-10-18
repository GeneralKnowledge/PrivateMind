from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from privatemind.vault.store import AccountKind, AccountRecord, CredentialVault


class ReadinessLevel(str, Enum):
    DORMANT = "dormant"
    PARTIAL = "partial"
    ALIVE = "alive"


@dataclass
class ReadinessReport:
    level: ReadinessLevel
    checks: list[dict[str, Any]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level.value,
            "checks": self.checks,
            "missing": self.missing,
        }


def assess_readiness(vault: CredentialVault) -> ReadinessReport:
    """
    README-driven bootstrap: minimum accounts before the agent is considered alive.

    Required for ALIVE:
    - At least one enabled LLM account OR heuristic-only mode flagged in public config
    - At least one enabled GitHub (SSH) account
    """
    report = ReadinessReport(level=ReadinessLevel.DORMANT)
    if not vault.exists:
        report.missing.append("Initialize vault: privatemind vault init")
        report.checks.append({"id": "vault", "ok": False, "detail": "not initialized"})
        return report

    if not vault.is_unlocked():
        report.missing.append("Unlock vault: export PRIVATE_MIND_VAULT_PASSPHRASE=... or use --passphrase")
        report.checks.append({"id": "vault_unlocked", "ok": False, "detail": "locked"})
        report.level = ReadinessLevel.DORMANT
        return report

    report.checks.append({"id": "vault_unlocked", "ok": True})
    accounts = [a for a in vault.list_accounts() if a.enabled]

    llm_accounts = [a for a in accounts if a.kind == AccountKind.LLM]
    github_accounts = [a for a in accounts if a.kind == AccountKind.GITHUB]
    ssh_accounts = [a for a in accounts if a.kind == AccountKind.SSH_HOST]

    has_llm = bool(llm_accounts)
    report.checks.append(
        {
            "id": "llm_account",
            "ok": has_llm,
            "detail": f"{len(llm_accounts)} enabled LLM account(s)",
            "hint": "Add with: privatemind account add llm --name primary ...",
        }
    )
    if not has_llm:
        report.missing.append("Add an LLM API account (privatemind account add llm --name primary)")

    has_github = bool(github_accounts)
    report.checks.append(
        {
            "id": "github_ssh_account",
            "ok": has_github,
            "detail": f"{len(github_accounts)} enabled GitHub SSH account(s)",
            "hint": "Add with: privatemind account add github --name agent-github ...",
        }
    )
    if not has_github:
        report.missing.append("Add a GitHub SSH account for git/ssh CLI access")

    for gh in github_accounts:
        transport = gh.public.get("transport", "ssh")
        report.checks.append(
            {
                "id": f"github:{gh.name}",
                "ok": transport == "ssh",
                "detail": f"transport={transport} (ssh preferred to avoid HTTP bot friction)",
            }
        )

    if ssh_accounts:
        report.checks.append(
            {
                "id": "ssh_hosts",
                "ok": True,
                "detail": f"{len(ssh_accounts)} test/server SSH account(s) configured",
            }
        )

    if has_llm and has_github:
        report.level = ReadinessLevel.ALIVE
    elif has_llm or has_github or ssh_accounts:
        report.level = ReadinessLevel.PARTIAL
    else:
        report.level = ReadinessLevel.DORMANT

    return report


def select_default_llm(accounts: list[AccountRecord]) -> AccountRecord | None:
    enabled = [a for a in accounts if a.enabled and a.kind == AccountKind.LLM]
    if not enabled:
        return None
    for preferred in ("primary", "default", "main"):
        for acct in enabled:
            if acct.name == preferred:
                return acct
    return enabled[0]


def select_default_github(accounts: list[AccountRecord]) -> AccountRecord | None:
    enabled = [a for a in accounts if a.enabled and a.kind == AccountKind.GITHUB]
    if not enabled:
        return None
    for preferred in ("agent-github", "github", "default"):
        for acct in enabled:
            if acct.name == preferred:
                return acct
    return enabled[0]
