import json
from pathlib import Path
from typing import Any

from privatemind.activation.readiness import ReadinessLevel, assess_readiness, select_default_github, select_default_llm
from privatemind.audit.log import AuditLog
from privatemind.executive.manager import TaskManager
from privatemind.integrations.git_cli import GitCli
from privatemind.integrations.ssh_material import materialize_ssh_private_key, ssh_target_command
from privatemind.memory.store import MemoryStore
from privatemind.models.factory import create_model_from_vault
from privatemind.trust import Provenance, TrustLevel
from privatemind.vault.store import AccountKind, CredentialVault
import subprocess


class WakeController:
    """Bring the agent from README configuration to running executive."""

    def __init__(
        self,
        *,
        vault: CredentialVault,
        tasks: TaskManager,
        memory: MemoryStore,
        audit: AuditLog,
        runtime_dir: Path,
    ) -> None:
        self.vault = vault
        self.tasks = tasks
        self.memory = memory
        self.audit = audit
        self.runtime_dir = runtime_dir
        self.git = GitCli(runtime_dir)

    def check(self) -> dict[str, Any]:
        return assess_readiness(self.vault).to_dict()

    def wake(self, *, run_health_checks: bool = True) -> dict[str, Any]:
        from privatemind.config import Settings
        from privatemind.operational.mode import operational_status

        settings = Settings(data_dir=self.runtime_dir.parent)
        result: dict[str, Any] = {
            "operational_mode": operational_status(
                settings.data_dir, env_mode=settings.operational_mode
            ),
        }
        report = assess_readiness(self.vault)
        result.update({"readiness": report.to_dict(), "health": [], "tasks": []})

        if report.level != ReadinessLevel.ALIVE:
            self.memory.upsert(
                kind="system",
                key="lifecycle.state",
                content=report.level.value,
                provenance=Provenance.TRUSTED_CORE,
                trust_level=TrustLevel.VERIFIED,
                metadata={"missing": report.missing},
            )
            result["activated"] = False
            return result

        accounts = self.vault.list_accounts()
        llm = select_default_llm(accounts)
        github = select_default_github(accounts)

        self.memory.upsert(
            kind="system",
            key="lifecycle.state",
            content="alive",
            provenance=Provenance.TRUSTED_CORE,
            trust_level=TrustLevel.VERIFIED,
        )
        mode_name = result.get("operational_mode", {}).get("mode")
        if mode_name:
            self.memory.upsert(
                kind="system",
                key="lifecycle.operational_mode",
                content=str(mode_name),
                provenance=Provenance.TRUSTED_CORE,
                trust_level=TrustLevel.VERIFIED,
            )
        self.memory.upsert(
            kind="system",
            key="accounts.primary_llm",
            content=llm.name if llm else "",
            provenance=Provenance.TRUSTED_CORE,
            trust_level=TrustLevel.VERIFIED,
        )
        self.memory.upsert(
            kind="system",
            key="accounts.primary_github",
            content=github.name if github else "",
            provenance=Provenance.TRUSTED_CORE,
            trust_level=TrustLevel.VERIFIED,
        )

        if run_health_checks and github:
            probe = self.git.probe_ssh(github)
            self.audit.record(
                "github_ssh_probe",
                account=github.name,
                ok=probe.ok,
                returncode=probe.returncode,
            )
            result["health"].append(
                {
                    "check": "github_ssh",
                    "account": github.name,
                    "ok": probe.ok,
                    "detail": (probe.stderr or probe.stdout).strip()[:500],
                }
            )

            repo_url = github.public.get("probe_repo_ssh_url")
            if repo_url and probe.ok:
                ls = self.git.ls_remote(github, str(repo_url))
                self.audit.record(
                    "git_ls_remote",
                    account=github.name,
                    repo=repo_url,
                    ok=ls.ok,
                    returncode=ls.returncode,
                )
                result["health"].append(
                    {
                        "check": "git_ls_remote",
                        "repo": repo_url,
                        "ok": ls.ok,
                        "detail": (ls.stderr or ls.stdout).strip()[:500],
                    }
                )

        for acct in accounts:
            if acct.kind != AccountKind.SSH_HOST or not acct.enabled:
                continue
            if not acct.public.get("run_wake_probe", True):
                continue
            try:
                key_path = materialize_ssh_private_key(acct, self.runtime_dir)
                cmd = ssh_target_command(acct, key_path) + ["echo", "privatemind-ok"]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
                ok = proc.returncode == 0 and "privatemind-ok" in proc.stdout
                self.audit.record(
                    "ssh_host_probe",
                    account=acct.name,
                    host=acct.public.get("host"),
                    ok=ok,
                    returncode=proc.returncode,
                )
                result["health"].append(
                    {
                        "check": "ssh_host",
                        "account": acct.name,
                        "ok": ok,
                        "detail": (proc.stderr or proc.stdout).strip()[:500],
                    }
                )
            except Exception as exc:  # noqa: BLE001 — health boundary
                result["health"].append(
                    {"check": "ssh_host", "account": acct.name, "ok": False, "detail": str(exc)}
                )

        bootstrap = self._ensure_bootstrap_task()
        if bootstrap:
            result["tasks"].append(bootstrap)

        result["activated"] = True
        result["model"] = create_model_from_vault(self.vault).model_id
        return result

    def _ensure_bootstrap_task(self) -> dict[str, Any] | None:
        existing = self.memory.get("system", "wake.bootstrap_task")
        if existing:
            task_id = existing.get("content")
            if task_id:
                task = self.tasks.get_task(str(task_id))
                if task:
                    return {"id": task.id, "title": task.title, "state": task.state.value}
            return None

        task = self.tasks.create_task(
            title="Post-wake bootstrap",
            description=(
                "Confirm lifecycle is alive, recall primary account names from memory, "
                "and store a short verified note under key wake.confirmed."
            ),
            priority=20,
        )
        meta = {"task_id": task.id}
        self.memory.upsert(
            kind="system",
            key="wake.bootstrap_task",
            content=task.id,
            provenance=Provenance.TRUSTED_CORE,
            trust_level=TrustLevel.VERIFIED,
            metadata=meta,
        )
        return {"id": task.id, "title": task.title, "state": task.state.value}
