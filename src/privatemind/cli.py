import json
from pathlib import Path

import click

from privatemind.cli_accounts import account_group, vault_group
from privatemind.cli_worker import worker_group
from privatemind.config import Settings
from privatemind.core.agent import PrivateMindCore
from privatemind.vault.passphrase import resolve_passphrase


def _core(data_dir: Path | None, *, unlock_vault: bool = True) -> PrivateMindCore:
    settings = Settings()
    if data_dir:
        settings = Settings(data_dir=data_dir)
    core = PrivateMindCore(settings=settings)
    if unlock_vault:
        core.ensure_vault_unlocked_from_env()
    return core


@click.group()
@click.option("--data-dir", type=click.Path(path_type=Path), default=None, help="Override data directory")
@click.pass_context
def main(ctx: click.Context, data_dir: Path | None) -> None:
    ctx.ensure_object(dict)
    ctx.obj["data_dir"] = data_dir


@main.command("init")
@click.pass_context
def init_cmd(ctx: click.Context) -> None:
    """Initialize database and seed capabilities."""
    core = _core(ctx.obj["data_dir"], unlock_vault=False)
    click.echo(f"Initialized PrivateMind at {core.settings.db_path}")
    if not core.vault.exists:
        click.echo("Next: privatemind vault init — then add accounts (see README).")


main.add_command(vault_group, name="vault")
main.add_command(account_group, name="account")
main.add_command(worker_group, name="worker")


@main.group()
@click.pass_context
def node(ctx: click.Context) -> None:
    """Core node identity (Ed25519)."""


@node.command("init")
@click.pass_context
def node_init(ctx: click.Context) -> None:
    from privatemind.worker.identity import NodeIdentity

    core = _core(ctx.obj["data_dir"], unlock_vault=False)
    path = core.settings.data_dir / "core_identity.json"
    if path.exists():
        raise click.ClickException("Core identity already exists")
    ident = NodeIdentity.generate("core")
    ident.save(path)
    click.echo(json.dumps({"fingerprint": ident.fingerprint, "public_key_b64": ident.public_key_b64}, indent=2))


@node.command("export-trust")
@click.option("--output", type=click.Path(path_type=Path), required=True)
@click.pass_context
def node_export_trust(ctx: click.Context, output: Path) -> None:
    """Export core Ed25519 public material for worker VMs (no private key)."""
    from privatemind.worker.identity import NodeIdentity
    from privatemind.worker.trusted_core import TrustedCore

    core = _core(ctx.obj["data_dir"], unlock_vault=False)
    path = core.settings.data_dir / "core_identity.json"
    if not path.is_file():
        raise click.ClickException("Run: privatemind node init")
    ident = NodeIdentity.load(path)
    TrustedCore(fingerprint=ident.fingerprint, public_key_b64=ident.public_key_b64).save(output)
    click.echo(json.dumps({"exported": str(output), "fingerprint": ident.fingerprint}, indent=2))


@main.command("setup-check")
@click.option("--passphrase", default=None)
@click.pass_context
def setup_check_cmd(ctx: click.Context, passphrase: str | None) -> None:
    """Report whether configured accounts are sufficient to wake the agent."""
    core = _core(ctx.obj["data_dir"], unlock_vault=False)
    if core.vault.exists:
        try:
            core.unlock_vault(resolve_passphrase(passphrase))
        except Exception as exc:  # noqa: BLE001
            click.echo(json.dumps({"error": str(exc), "hint": "Set PRIVATE_MIND_VAULT_PASSPHRASE"}))
            return
    from privatemind.activation.worker_health import merge_setup_report, worker_network_report

    readiness = core.wake.check()
    worker_report = None
    if core.core_identity:
        worker_report = worker_network_report(core.pairing)
    click.echo(json.dumps(merge_setup_report(readiness, worker_report), indent=2))


@main.command("wake")
@click.option("--passphrase", default=None)
@click.option("--skip-health", is_flag=True, help="Skip git/ssh probes")
@click.option("--run/--no-run", default=False, help="Run executive until idle after wake")
@click.pass_context
def wake_cmd(ctx: click.Context, passphrase: str | None, skip_health: bool, run: bool) -> None:
    """Validate accounts and transition the agent from dormant to alive."""
    core = _core(ctx.obj["data_dir"], unlock_vault=False)
    if not core.vault.exists:
        raise click.ClickException("Configure the vault first (see README): privatemind vault init")
    core.unlock_vault(resolve_passphrase(passphrase))
    from privatemind.models.factory import create_model

    core.model = create_model(core.settings, core.vault)
    outcome = core.wake.wake(run_health_checks=not skip_health)
    click.echo(json.dumps(outcome, indent=2))
    if run and outcome.get("activated"):
        results = core.run_until_idle()
        click.echo(json.dumps({"executive": results}, indent=2))


@main.command("demo")
@click.option("--run", is_flag=True, help="Create demo task and run until idle")
@click.pass_context
def demo_cmd(ctx: click.Context, run: bool) -> None:
    """Milestone 1 demo: hash, remember, recover across restarts."""
    core = _core(ctx.obj["data_dir"])
    task = core.bootstrap_demo()
    click.echo(f"Demo task: {task.id} ({task.state.value})")
    if run:
        results = core.run_until_idle()
        click.echo(json.dumps(results, indent=2))


@main.command("tick")
@click.option("--steps", default=1, show_default=True)
@click.pass_context
def tick_cmd(ctx: click.Context, steps: int) -> None:
    """Advance the executive by up to N task steps."""
    core = _core(ctx.obj["data_dir"])
    results = core.tick(max_steps=steps)
    click.echo(json.dumps(results, indent=2))


@main.command("status")
@click.pass_context
def status_cmd(ctx: click.Context) -> None:
    """Show tasks, checkpoint, and pending human requests."""
    core = _core(ctx.obj["data_dir"])
    tasks = core.tasks.list_tasks()
    checkpoint = core.tasks.get_checkpoint()
    pending = core.assistance.list_pending()
    from privatemind.activation.worker_health import worker_network_report

    worker_report = worker_network_report(core.pairing) if core.core_identity else None
    pending_tools = core.tool_requests.list_pending()
    caps = core.capabilities.list_enabled()
    payload = {
        "db_path": str(core.settings.db_path),
        "checkpoint": checkpoint,
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "state": t.state.value,
                "priority": t.priority,
                "retry_count": t.retry_count,
                "blocker": t.blocker_reason,
            }
            for t in tasks
        ],
        "pending_human_requests": pending,
        "pending_tool_requests": len(pending_tools),
        "enabled_capabilities": len(caps),
        "worker_network": worker_report,
        "lifecycle": core.memory.get("system", "lifecycle.state"),
    }
    click.echo(json.dumps(payload, indent=2))


@main.command("task")
@click.argument("title")
@click.option("--description", default="", show_default=True)
@click.option("--priority", default=0, show_default=True)
@click.pass_context
def task_cmd(ctx: click.Context, title: str, description: str, priority: int) -> None:
    """Enqueue a new task."""
    core = _core(ctx.obj["data_dir"])
    task = core.tasks.create_task(title=title, description=description, priority=priority)
    click.echo(json.dumps({"id": task.id, "title": task.title, "state": task.state.value}))


@main.group("memory")
@click.pass_context
def memory_group(ctx: click.Context) -> None:
    """Search and promote memory trust levels."""


def _memory_search(ctx: click.Context, query: str | None, kind: str | None) -> None:
    core = _core(ctx.obj["data_dir"])
    rows = core.memory.search(query=query, kind=kind)
    click.echo(json.dumps(rows, indent=2))


@memory_group.command("search")
@click.option("--query", default=None)
@click.option("--kind", default=None)
@click.pass_context
def memory_search_cmd(ctx: click.Context, query: str | None, kind: str | None) -> None:
    _memory_search(ctx, query, kind)


@memory_group.command("promote")
@click.option("--kind", required=True)
@click.option("--key", required=True)
@click.option(
    "--level",
    "target_level",
    required=True,
    type=click.Choice(["partially_verified", "verified", "rejected"]),
)
@click.option("--evidence", required=True, help="Why this promotion is justified")
@click.pass_context
def memory_promote_cmd(
    ctx: click.Context,
    kind: str,
    key: str,
    target_level: str,
    evidence: str,
) -> None:
    from privatemind.memory.promotion import promote_memory_trust
    from privatemind.trust import TrustLevel

    core = _core(ctx.obj["data_dir"])
    level = TrustLevel(target_level)
    result = promote_memory_trust(core.memory, kind=kind, key=key, target_level=level, evidence=evidence)
    if not result.get("ok"):
        raise click.ClickException(str(result.get("error")))
    core.audit.record("memory_promoted", **result)
    click.echo(json.dumps(result, indent=2))


@main.command("memory-search")
@click.option("--query", default=None)
@click.option("--kind", default=None)
@click.pass_context
def memory_search_legacy(ctx: click.Context, query: str | None, kind: str | None) -> None:
    """Deprecated alias for `privatemind memory search`."""
    _memory_search(ctx, query, kind)


@main.command("help-request")
@click.argument("question")
@click.pass_context
def help_request_cmd(ctx: click.Context, question: str) -> None:
    core = _core(ctx.obj["data_dir"])
    req_id = core.assistance.create_request(question)
    click.echo(json.dumps({"request_id": req_id, "status": "pending"}))


@main.command("help-answer")
@click.argument("request_id")
@click.argument("response")
@click.pass_context
def help_answer_cmd(ctx: click.Context, request_id: str, response: str) -> None:
    core = _core(ctx.obj["data_dir"])
    ok = core.assistance.answer(request_id, response)
    if ok:
        core.resume_after_human_answer(request_id)
    click.echo(json.dumps({"request_id": request_id, "answered": ok}))


@main.group()
@click.pass_context
def improve(ctx: click.Context) -> None:
    """Self-improvement workspace and git-over-SSH tools."""


@improve.command("start")
@click.option("--repo-ssh-url", required=True, help="git@github.com:org/repo.git")
@click.option("--workspace", required=True, help="Name under ~/.privatemind/workspaces/")
@click.option("--branch", default="cursor/self-improve", show_default=True)
@click.option("--run", is_flag=True, help="Run executive after enqueue")
@click.pass_context
def improve_start_cmd(
    ctx: click.Context,
    repo_ssh_url: str,
    workspace: str,
    branch: str,
    run: bool,
) -> None:
    core = _core(ctx.obj["data_dir"])
    if not core.vault.is_unlocked():
        core.unlock_vault(resolve_passphrase(None))
    task = core.start_improvement(repo_ssh_url=repo_ssh_url, workspace=workspace, branch=branch)
    click.echo(json.dumps({"task_id": task.id, "title": task.title, "state": task.state.value}))
    if run:
        click.echo(json.dumps(core.run_until_idle(), indent=2))


@improve.command("seed-workspace")
@click.option("--workspace", required=True)
@click.option(
    "--from-path",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.pass_context
def improve_seed_workspace(ctx: click.Context, workspace: str, from_path: Path) -> None:
    """Copy a local directory into an isolated workspace (offline self-improvement)."""
    from privatemind.improvement.workflow import seed_workspace_from_path

    core = _core(ctx.obj["data_dir"], unlock_vault=False)
    seed_workspace_from_path(core.workspaces, workspace, from_path)
    click.echo(json.dumps({"workspace": workspace, "path": str(core.workspaces.resolve(workspace))}))


@improve.command("run-local")
@click.option("--workspace", default="local-lab")
@click.option("--from-path", type=click.Path(exists=True, file_okay=False, path_type=Path), default=None)
@click.option("--branch", default="cursor/self-improve-local")
@click.pass_context
def improve_run_local(ctx: click.Context, workspace: str, from_path: Path | None, branch: str) -> None:
    """Seed workspace (optional), enqueue self-improvement task, run trusted workflow."""
    from privatemind.improvement.workflow import seed_workspace_from_path

    core = _core(ctx.obj["data_dir"])
    if from_path:
        seed_workspace_from_path(core.workspaces, workspace, from_path)
    task = core.start_improvement(
        repo_ssh_url="git@github.com:local/seed.git",
        workspace=workspace,
        branch=branch,
    )
    results = core.run_until_idle(max_iterations=40)
    click.echo(json.dumps({"task_id": task.id, "steps": results}, indent=2))


@improve.command("limitations")
@click.pass_context
def improve_limitations_cmd(ctx: click.Context) -> None:
    """List recorded limitations (trusted-core ledger)."""
    core = _core(ctx.obj["data_dir"], unlock_vault=False)
    rows = core.memory.search(kind="limitation", limit=100)
    click.echo(json.dumps({"limitations": rows}, indent=2))


@improve.command("clone")
@click.option("--repo-ssh-url", required=True)
@click.option("--workspace", required=True)
@click.option("--github-account", default="agent-github", show_default=True)
@click.pass_context
def improve_clone_cmd(ctx: click.Context, repo_ssh_url: str, workspace: str, github_account: str) -> None:
    core = _core(ctx.obj["data_dir"])
    if not core.vault.is_unlocked():
        core.unlock_vault(resolve_passphrase(None))
    result = core.tools.invoke(
        "git_clone",
        {
            "repo_ssh_url": repo_ssh_url,
            "workspace": workspace,
            "github_account": github_account,
        },
    )
    click.echo(json.dumps({"ok": result.ok, "output": result.output, "detail": result.detail}, indent=2))


@main.command("workspaces")
@click.pass_context
def workspaces_cmd(ctx: click.Context) -> None:
    core = _core(ctx.obj["data_dir"], unlock_vault=False)
    click.echo(json.dumps({"workspaces": core.workspaces.list_workspaces()}, indent=2))


@main.group()
@click.pass_context
def research(ctx: click.Context) -> None:
    """Probe and catalog free / cheap-tier services (agent recon)."""


@research.command("probe-api")
@click.option("--base-url", required=True, help="OpenAI-compatible root, e.g. https://integrate.api.nvidia.com/v1")
@click.option("--api-key-env", default=None, help="Env var name holding the API key (not printed)")
@click.pass_context
def research_probe_api(ctx: click.Context, base_url: str, api_key_env: str | None) -> None:
    import os

    from privatemind.research.probe import probe_openai_compatible

    key = os.environ.get(api_key_env) if api_key_env else None
    result = probe_openai_compatible(base_url=base_url, api_key=key)
    click.echo(json.dumps(result, indent=2))


@research.command("probe-nim")
@click.option("--api-key-env", default="NVIDIA_API_KEY", show_default=True)
@click.pass_context
def research_probe_nim(ctx: click.Context, api_key_env: str) -> None:
    """Probe NVIDIA hosted NIM catalog (integrate.api.nvidia.com)."""
    import os

    from privatemind.research.probe import probe_openai_compatible

    key = os.environ.get(api_key_env) or os.environ.get("NGC_API_KEY")
    if not key:
        raise click.ClickException(f"Set {api_key_env} or NGC_API_KEY")
    result = probe_openai_compatible(base_url="https://integrate.api.nvidia.com/v1", api_key=key)
    click.echo(json.dumps(result, indent=2))


@research.command("candidate")
@click.argument("slug")
@click.option("--name", required=True)
@click.option("--category", required=True, help="llm | gpu/batch | host | webhook | other")
@click.option("--docs-url", default="")
@click.option("--notes", default="")
@click.option(
    "--verdict",
    default="pending",
    type=click.Choice(["pending", "useful", "reject"]),
)
@click.pass_context
def research_candidate_log(
    ctx: click.Context,
    slug: str,
    name: str,
    category: str,
    docs_url: str,
    notes: str,
    verdict: str,
) -> None:
    from privatemind.research.candidates import log_candidate

    core = _core(ctx.obj["data_dir"], unlock_vault=False)
    log_candidate(
        core.memory,
        slug=slug,
        name=name,
        category=category,
        docs_url=docs_url,
        notes=notes,
        verdict=verdict,
    )
    click.echo(json.dumps({"logged": slug, "verdict": verdict}))


@research.command("candidates")
@click.option("--verdict", default=None, type=click.Choice(["pending", "useful", "reject"]))
@click.pass_context
def research_candidates_list(ctx: click.Context, verdict: str | None) -> None:
    from privatemind.research.candidates import list_candidates

    core = _core(ctx.obj["data_dir"], unlock_vault=False)
    click.echo(json.dumps({"candidates": list_candidates(core.memory, verdict=verdict)}, indent=2))


@main.group()
@click.pass_context
def tool_request(ctx: click.Context) -> None:
    """Queue and approve new tools (dedicated-server expansion)."""


@tool_request.command("list")
@click.pass_context
def tool_request_list(ctx: click.Context) -> None:
    core = _core(ctx.obj["data_dir"], unlock_vault=False)
    pending = core.tool_requests.list_pending()
    click.echo(json.dumps({"pending": pending}, indent=2))


@tool_request.command("approve")
@click.argument("request_id")
@click.option("--capability-id", default=None, help="Defaults to tool.requested.<name>")
@click.option(
    "--runner-arg",
    "runner_argv",
    multiple=True,
    help="Subprocess argv for approved tool (receives JSON on stdin). Example: --runner-arg python3 --runner-arg -c --runner-arg script",
)
@click.option("--sandbox-memory-mb", type=int, default=None)
@click.option("--sandbox-network/--no-sandbox-network", default=None)
@click.pass_context
def tool_request_approve(
    ctx: click.Context,
    request_id: str,
    capability_id: str | None,
    runner_argv: tuple[str, ...],
    sandbox_memory_mb: int | None,
    sandbox_network: bool | None,
) -> None:
    from privatemind.capabilities.registry import Capability

    core = _core(ctx.obj["data_dir"], unlock_vault=False)
    row = core.tool_requests.get(request_id)
    if not row:
        raise click.ClickException("Request not found")
    cap_id = capability_id or f"tool.requested.{row['tool_name'].replace(' ', '_')[:40]}"
    limits: dict = {"granted_via": "tool_request", "request_id": request_id}
    if runner_argv:
        limits["runner_argv"] = list(runner_argv)
    if sandbox_memory_mb is not None:
        limits["sandbox_memory_mb"] = sandbox_memory_mb
    if sandbox_network is not None:
        limits["sandbox_network"] = sandbox_network
    core.capabilities.register(
        Capability(
            id=cap_id,
            name=f"Requested: {row['tool_name']}",
            kind="tool",
            description=row["purpose"],
            operations=[row["tool_name"]],
            limits=limits,
            trust={"runs_locally": True, "operator_approved": True, "isolation": "subprocess"},
            enabled=True,
        )
    )
    ok = core.tool_requests.approve(request_id, capability_id=cap_id)
    core.audit.record("tool_request_approved", request_id=request_id, capability_id=cap_id)
    click.echo(json.dumps({"approved": ok, "capability_id": cap_id}))


@tool_request.command("reject")
@click.argument("request_id")
@click.pass_context
def tool_request_reject(ctx: click.Context, request_id: str) -> None:
    core = _core(ctx.obj["data_dir"], unlock_vault=False)
    ok = core.tool_requests.reject(request_id)
    click.echo(json.dumps({"rejected": ok}))


@main.command("capabilities")
@click.pass_context
def capabilities_cmd(ctx: click.Context) -> None:
    core = _core(ctx.obj["data_dir"])
    caps = core.capabilities.list_enabled()
    click.echo(
        json.dumps(
            [
                {
                    "id": c.id,
                    "name": c.name,
                    "kind": c.kind,
                    "operations": c.operations,
                    "limits": c.limits,
                }
                for c in caps
            ],
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
