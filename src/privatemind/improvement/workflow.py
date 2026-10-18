import json
import re
import shutil
from dataclasses import dataclass
from typing import Any

from privatemind.executive.tasks import Task, TaskState
from privatemind.improvement.manifest import ImprovementManifest, ImprovementPhase
from privatemind.security.policy import diff_touches_sensitive
from privatemind.security.protected_manifest import diff_touches_protected
from privatemind.trust import Provenance, TrustLevel


@dataclass
class ImprovementContext:
    workspace: str
    repo_ssh_url: str | None
    branch: str


def parse_improvement_context(description: str) -> ImprovementContext:
    ws = re.search(r"Workspace:\s*(\S+)", description)
    branch = re.search(r"Target branch:\s*(\S+)", description)
    repo = re.search(r"Repository \(SSH only\):\s*(\S+)", description)
    return ImprovementContext(
        workspace=ws.group(1) if ws else "default",
        repo_ssh_url=repo.group(1) if repo else None,
        branch=branch.group(1) if branch else "cursor/self-improve",
    )


class ImprovementWorkflow:
    """Trusted self-improvement state machine (survives restarts via manifest)."""

    TITLE_PREFIX = "Self-improvement:"

    def __init__(self, core: Any) -> None:
        self._core = core

    def handles(self, task: Task) -> bool:
        return task.title.startswith(self.TITLE_PREFIX)

    def run_step(self, task: Task) -> dict[str, Any]:
        manifest = ImprovementManifest(self._core.memory, task.id)
        ctx = parse_improvement_context(task.description)
        data = manifest.load()
        phase = ImprovementPhase(data.get("phase", ImprovementPhase.INIT.value))

        if phase == ImprovementPhase.DONE:
            self._core.tasks.mark_completed(task, summary="Self-improvement already completed")
            return {"task_id": task.id, "state": task.state.value, "completed": True}

        if phase == ImprovementPhase.FAILED:
            return {"task_id": task.id, "state": task.state.value, "failed": True}

        if phase == ImprovementPhase.INIT:
            return self._phase_init(task, manifest, ctx)

        if phase == ImprovementPhase.DISCOVER:
            return self._phase_discover(task, manifest, ctx)

        if phase == ImprovementPhase.INVESTIGATE:
            return self._phase_investigate(task, manifest, ctx)

        if phase == ImprovementPhase.IMPLEMENT:
            return self._phase_implement(task, manifest, ctx)

        if phase == ImprovementPhase.VERIFY:
            return self._phase_verify(task, manifest, ctx)

        if phase == ImprovementPhase.SUBMIT:
            return self._phase_submit(task, manifest, ctx)

        if phase == ImprovementPhase.RECORD:
            return self._phase_record(task, manifest, ctx)

        return self._fail(task, manifest, f"Unknown phase: {phase}")

    def _phase_init(self, task: Task, manifest: ImprovementManifest, ctx: ImprovementContext) -> dict[str, Any]:
        ws_path = self._core.workspaces.resolve(ctx.workspace)
        if ws_path.exists() and any(ws_path.iterdir()):
            manifest.checkpoint("clone_done")
        elif ctx.repo_ssh_url and not manifest.has_checkpoint("clone_done"):
            result = self._core.tools.invoke(
                "git_clone",
                {
                    "repo_ssh_url": ctx.repo_ssh_url,
                    "workspace": ctx.workspace,
                    "github_account": "agent-github",
                },
                task_id=task.id,
            )
            if not result.ok and "not empty" not in (result.detail or ""):
                return self._fail(task, manifest, f"git_clone failed: {result.detail}")
            manifest.checkpoint("clone_done")
        manifest.set_phase(ImprovementPhase.DISCOVER)
        task.state = TaskState.PENDING
        self._core.tasks._save(task)  # noqa: SLF001
        return {"task_id": task.id, "phase": ImprovementPhase.DISCOVER.value}

    def _phase_discover(self, task: Task, manifest: ImprovementManifest, ctx: ImprovementContext) -> dict[str, Any]:
        if not manifest.has_checkpoint("discovered"):
            notes = self._core.tools.invoke(
                "repo_read_file",
                {"workspace": ctx.workspace, "path": "docs/NOTES.md"},
                task_id=task.id,
            )
            listing = self._core.tools.invoke(
                "repo_list_dir",
                {"workspace": ctx.workspace, "path": "src"},
                task_id=task.id,
            )
            self._store_tool_trace(task, "discover", {"notes": notes.output, "listing": listing.output})
            manifest.checkpoint("discovered")
        manifest.set_phase(ImprovementPhase.INVESTIGATE)
        task.state = TaskState.PENDING
        self._core.tasks._save(task)  # noqa: SLF001
        return {"task_id": task.id, "phase": ImprovementPhase.INVESTIGATE.value}

    def _phase_investigate(
        self, task: Task, manifest: ImprovementManifest, ctx: ImprovementContext
    ) -> dict[str, Any]:
        if not manifest.has_checkpoint("limitation_recorded"):
            tests = self._core.tools.invoke(
                "run_tests",
                {"workspace": ctx.workspace, "command": "python3 -m pytest -q"},
                task_id=task.id,
            )
            calc = self._core.tools.invoke(
                "repo_read_file",
                {"workspace": ctx.workspace, "path": "src/calc.py"},
                task_id=task.id,
            )
            evidence = json.dumps(
                {
                    "tests": tests.output,
                    "calc_excerpt": (calc.output or {}).get("content", "")[:500] if calc.ok else calc.detail,
                }
            )
            if tests.ok:
                manifest.checkpoint("limitation_recorded")
                manifest.checkpoint("tests_already_passing")
            else:
                self._core.tools.invoke(
                    "record_limitation",
                    {
                        "key": f"task-{task.id}-calc-add",
                        "summary": "calc.add returns product instead of sum",
                        "evidence": evidence,
                        "severity": "medium",
                        "component": "src/calc.py",
                        "status": "confirmed",
                    },
                    task_id=task.id,
                )
                manifest.checkpoint("limitation_recorded")
        manifest.set_phase(ImprovementPhase.IMPLEMENT)
        task.state = TaskState.PENDING
        self._core.tasks._save(task)  # noqa: SLF001
        return {"task_id": task.id, "phase": ImprovementPhase.IMPLEMENT.value}

    def _phase_implement(
        self, task: Task, manifest: ImprovementManifest, ctx: ImprovementContext
    ) -> dict[str, Any]:
        if manifest.has_checkpoint("tests_already_passing"):
            manifest.set_phase(ImprovementPhase.VERIFY)
            return {"task_id": task.id, "phase": ImprovementPhase.VERIFY.value, "skipped_implement": True}

        if not manifest.has_checkpoint("fix_applied"):
            calc = self._core.tools.invoke(
                "repo_read_file",
                {"workspace": ctx.workspace, "path": "src/calc.py"},
                task_id=task.id,
            )
            if not calc.ok:
                return self._fail(task, manifest, calc.detail or "cannot read calc.py")
            content = str((calc.output or {}).get("content", ""))
            if "return a * b" not in content:
                return self._fail(task, manifest, "expected bug pattern not found; refusing blind edit")
            fixed = content.replace("return a * b", "return a + b", 1)
            write = self._core.tools.invoke(
                "repo_write_file",
                {"workspace": ctx.workspace, "path": "src/calc.py", "content": fixed},
                task_id=task.id,
            )
            if not write.ok:
                return self._fail(task, manifest, write.detail or "write failed")
            manifest.checkpoint("fix_applied")
        manifest.set_phase(ImprovementPhase.VERIFY)
        task.state = TaskState.PENDING
        self._core.tasks._save(task)  # noqa: SLF001
        return {"task_id": task.id, "phase": ImprovementPhase.VERIFY.value}

    def _phase_verify(self, task: Task, manifest: ImprovementManifest, ctx: ImprovementContext) -> dict[str, Any]:
        tests = self._core.tools.invoke(
            "run_tests",
            {"workspace": ctx.workspace, "command": "python3 -m pytest -q"},
            task_id=task.id,
        )
        diff = self._core.tools.invoke(
            "git_diff",
            {"workspace": ctx.workspace, "staged": False},
            task_id=task.id,
        )
        data = manifest.load()
        data["tests_passed"] = bool(tests.ok)
        data["verify_passed"] = bool(tests.ok)
        if diff.ok and isinstance(diff.output, dict):
            diff_text = str(diff.output.get("stdout", ""))
            sensitive = sorted(set(diff_touches_sensitive(diff_text) + diff_touches_protected(diff_text)))
            if sensitive:
                data["security_review_required"] = True
                data["sensitive_paths"] = sensitive
        manifest.save(data)

        if not tests.ok:
            return self._fail(task, manifest, "verification failed: tests did not pass")

        manifest.set_phase(ImprovementPhase.SUBMIT)
        task.state = TaskState.PENDING
        self._core.tasks._save(task)  # noqa: SLF001
        return {"task_id": task.id, "phase": ImprovementPhase.SUBMIT.value, "tests_passed": True}

    def _phase_submit(self, task: Task, manifest: ImprovementManifest, ctx: ImprovementContext) -> dict[str, Any]:
        data = manifest.load()
        if data.get("security_review_required"):
            self._core.tasks.mark_blocked(task, "security_review_required")
            self._core.tools.invoke(
                "request_human_help",
                {
                    "question": "Approve security-sensitive self-improvement changes?",
                    "context": {"paths": data.get("sensitive_paths", [])},
                },
                task_id=task.id,
            )
            return {"task_id": task.id, "state": task.state.value, "blocked": "security_review"}

        ws = self._core.workspaces.resolve(ctx.workspace)
        if (ws / ".git").is_dir():
            if not manifest.has_checkpoint("branch_ready"):
                branch_result = self._core.tools.invoke(
                    "git_branch",
                    {"workspace": ctx.workspace, "branch": ctx.branch, "create": True},
                    task_id=task.id,
                )
                if not branch_result.ok and "already exists" not in (branch_result.detail or "").lower():
                    # checkout may fail if branch exists; continue
                    pass
                manifest.checkpoint("branch_ready")

            if not manifest.has_checkpoint("commit_done"):
                commit = self._core.tools.invoke(
                    "git_commit",
                    {
                        "workspace": ctx.workspace,
                        "message": "fix: correct calc.add self-improvement cycle",
                        "paths": ["src/calc.py"],
                    },
                    task_id=task.id,
                )
                if not commit.ok:
                    return self._fail(task, manifest, commit.detail or "commit failed")
                manifest.checkpoint("commit_done")

            if not manifest.has_checkpoint("push_done") and ctx.repo_ssh_url:
                push = self._core.tools.invoke(
                    "git_push",
                    {"workspace": ctx.workspace, "branch": ctx.branch, "github_account": "agent-github"},
                    task_id=task.id,
                )
                if push.ok:
                    manifest.checkpoint("push_done")
                else:
                    # Local-only workspaces may lack remote; still allow record phase.
                    manifest.checkpoint("push_skipped", push.detail or "push failed")

            if manifest.has_checkpoint("push_done") and not manifest.has_checkpoint("pr_created"):
                from privatemind.integrations.gh_cli import (
                    create_draft_pull_request,
                    format_improvement_pr_body,
                    gh_available,
                )

                if gh_available():
                    pr = create_draft_pull_request(
                        workspace=ws,
                        branch=ctx.branch,
                        title="Self-improvement: trusted workflow submission",
                        body=format_improvement_pr_body(
                            task_id=task.id,
                            workspace=ctx.workspace,
                            tests_passed=bool(data.get("tests_passed")),
                        ),
                    )
                    if pr.ok:
                        manifest.checkpoint("pr_created")
                        data["pr_url"] = pr.pr_url or pr.stdout.strip()
                        manifest.save(data)
                    else:
                        data["pr_error"] = (pr.stderr or pr.stdout)[:500]
                        manifest.save(data)

        manifest.set_phase(ImprovementPhase.RECORD)
        task.state = TaskState.PENDING
        self._core.tasks._save(task)  # noqa: SLF001
        return {"task_id": task.id, "phase": ImprovementPhase.RECORD.value}

    def _phase_record(self, task: Task, manifest: ImprovementManifest, ctx: ImprovementContext) -> dict[str, Any]:
        data = manifest.load()
        if not data.get("verify_passed"):
            return self._fail(task, manifest, "cannot record success without verify_passed")

        self._core.improvements.record_outcome(
            key=f"outcome-{task.id}",
            limitation_key=f"task-{task.id}-calc-add",
            success=True,
            notes="Self-improvement cycle completed with passing tests",
            metrics={"workspace": ctx.workspace, "branch": ctx.branch},
        )
        manifest.set_phase(ImprovementPhase.DONE)
        self._core.tasks.mark_completed(task, summary="Self-improvement cycle completed")
        self._core.tasks.set_checkpoint(None, notes="Idle")
        return {"task_id": task.id, "state": task.state.value, "completed": True}

    def _fail(self, task: Task, manifest: ImprovementManifest, reason: str) -> dict[str, Any]:
        data = manifest.load()
        data["failure_reason"] = reason
        manifest.save(data)
        manifest.set_phase(ImprovementPhase.FAILED)
        self._core.improvements.record_outcome(
            key=f"outcome-{task.id}",
            limitation_key=f"task-{task.id}-calc-add",
            success=False,
            notes=reason,
        )
        self._core.tasks.mark_failed(task, reason, retry=False)
        return {"task_id": task.id, "state": task.state.value, "error": reason}

    def _store_tool_trace(self, task: Task, label: str, payload: dict[str, Any]) -> None:
        self._core.memory.upsert(
            kind="tool_trace",
            key=f"{task.id}:{label}",
            content=json.dumps(payload)[:100_000],
            provenance=Provenance.TOOL_OUTPUT,
            trust_level=TrustLevel.UNVERIFIED,
            metadata={"task_id": task.id},
        )


def seed_workspace_from_path(layout: Any, name: str, source: Any) -> None:
    dest = layout.resolve(name)
    if dest.exists():
        return
    shutil.copytree(source, dest)
