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


@research.command("probe-brave-search")
@click.option("--api-key-env", default="BRAVE_SEARCH_API_KEY", show_default=True)
@click.option("--query", default="PrivateMind")
@click.pass_context
def research_probe_brave_search(ctx: click.Context, api_key_env: str, query: str) -> None:
    """Probe Brave Search API web endpoint (SERP)."""
    import os

    from privatemind.research.probe import probe_brave_web_search

    key = os.environ.get(api_key_env)
    if not key:
        raise click.ClickException(f"Set {api_key_env}")
    click.echo(json.dumps(probe_brave_web_search(api_key=key, query=query), indent=2))


@research.command("capability-domains")
@click.pass_context
def research_capability_domains(ctx: click.Context) -> None:
    """Domains the agent should pursue (email, SMS, wallets, etc.)."""
    from privatemind.research.capability_domains import load_capability_domains, list_domains

    meta = load_capability_domains()
    click.echo(
        json.dumps(
            {
                "schema_version": meta.get("schema_version"),
                "trust_ladder": meta.get("trust_ladder"),
                "domains": list_domains(meta),
                "mandate_doc": "docs/AGENT_CAPABILITY_MANDATE.md",
            },
            indent=2,
        )
    )


@research.command("self-model")
@click.pass_context
def research_self_model(ctx: click.Context) -> None:
    """Mind layers skeleton and empty self-map graph (agent extends)."""
    from privatemind.research.self_model import load_self_model, list_layers

    meta = load_self_model()
    click.echo(
        json.dumps(
            {
                "schema_version": meta.get("schema_version"),
                "layers": list_layers(meta),
                "layers_seed_note": meta.get("layers_seed_note"),
                "food_metaphor": meta.get("food_metaphor"),
                "layer_extensions": meta.get("layer_extensions", []),
                "needs": meta.get("needs", []),
                "activity_modes": meta.get("activity_modes", []),
                "graph": meta.get("graph"),
                "routing_policies": meta.get("routing_policies", []),
                "vocabulary": meta.get("vocabulary"),
                "mind_layers_doc": meta.get("mind_layers_doc"),
                "helper_playbooks_index": meta.get("helper_playbooks_index"),
            },
            indent=2,
        )
    )


@research.command("self-model-status")
@click.pass_context
def research_self_model_status(ctx: click.Context) -> None:
    """Counts for needs/graph — nudge to self-organise."""
    from privatemind.research.self_model import self_model_status

    click.echo(json.dumps(self_model_status(), indent=2))


@research.command("helper-playbooks")
@click.pass_context
def research_helper_playbooks(ctx: click.Context) -> None:
    """Index of donor/helper instruction playbooks (agent-authored)."""
    from privatemind.research.helper_playbooks import load_helper_playbooks, list_playbooks

    meta = load_helper_playbooks()
    click.echo(
        json.dumps(
            {
                "schema_version": meta.get("schema_version"),
                "instructions_doc": meta.get("instructions_doc"),
                "helpers_dir": meta.get("helpers_dir"),
                "non_key_help_examples": meta.get("non_key_help_examples"),
                "playbooks": list_playbooks(meta),
            },
            indent=2,
        )
    )


@research.command("capability-gaps")
@click.pass_context
def research_capability_gaps(ctx: click.Context) -> None:
    """Compare vault accounts to desired capability domains."""
    from privatemind.vault.passphrase import resolve_passphrase
    from privatemind.research.capability_domains import capability_gaps

    core = _core(ctx.obj["data_dir"], unlock_vault=False)
    vault = None
    try:
        core.unlock_vault(resolve_passphrase(None))
        vault = core.vault
    except Exception:  # noqa: BLE001
        vault = None
    click.echo(json.dumps(capability_gaps(vault), indent=2))


@research.command("tool-entitlements")
@click.option("--class", "eligibility_class", default=None, type=click.Choice(["A", "B", "C"]))
@click.option("--tool-kind", default=None, type=click.Choice(["serp", "instant_answer", "serp_agent", "neural_search", "knowledge_lookup"]))
@click.option("--provider-id", default=None)
@click.pass_context
def research_tool_entitlements(
    ctx: click.Context,
    eligibility_class: str | None,
    tool_kind: str | None,
    provider_id: str | None,
) -> None:
    """List web search / grounding tool rows (non-LLM catalogue)."""
    from privatemind.research.tool_entitlements import list_tool_entries, load_tool_entitlements

    data = load_tool_entitlements()
    rows = list_tool_entries(
        data,
        eligibility_class=eligibility_class,
        tool_kind=tool_kind,
        provider_id=provider_id,
    )
    click.echo(
        json.dumps(
            {
                "schema_version": data.get("schema_version"),
                "count": len(rows),
                "entries": rows,
            },
            indent=2,
        )
    )


@research.command("candidate")
@click.argument("slug")
@click.option("--name", required=True)
@click.option("--category", required=True, help="llm | search | gpu/batch | host | webhook | other")
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


@research.command("provider-catalog")
@click.option("--provider-id", default=None, help="Show one provider entry by quota-file key (e.g. nvidia_nim)")
@click.pass_context
def research_provider_catalog(ctx: click.Context, provider_id: str | None) -> None:
    from privatemind.research.provider_catalog import load_catalog

    cat = load_catalog()
    providers = cat.get("providers", {})
    if provider_id:
        entry = providers.get(provider_id)
        if entry is None:
            raise click.ClickException(f"Unknown provider id: {provider_id}")
        click.echo(json.dumps({provider_id: entry}, indent=2))
        return
    click.echo(
        json.dumps(
            {
                "schema_version": cat.get("schema_version"),
                "provider_ids": sorted(providers.keys()),
                "catalog_path": "docs/data/free_tier_provider_catalog.json",
            },
            indent=2,
        )
    )


@research.command("quota-diff")
@click.argument("quota_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def research_quota_diff(ctx: click.Context, quota_file: Path) -> None:
    """Compare a runtime quota JSON file to the repo provider catalog."""
    from privatemind.research.provider_catalog import diff_quota_state, load_quota_state

    quota = load_quota_state(quota_file)
    click.echo(json.dumps(diff_quota_state(quota), indent=2))


@research.command("seed-catalog")
@click.option("--force", is_flag=True, help="Re-log catalog rows even if slug already exists")
@click.pass_context
def research_seed_catalog(ctx: click.Context, force: bool) -> None:
    """Seed memory candidates from docs/data/free_tier_provider_catalog.json."""
    from privatemind.research.provider_catalog import seed_candidates_from_catalog

    core = _core(ctx.obj["data_dir"], unlock_vault=False)
    result = seed_candidates_from_catalog(core.memory, skip_existing=not force)
    click.echo(json.dumps(result, indent=2))


@research.command("entitlements")
@click.option("--class", "eligibility_class", default=None, type=click.Choice(["A", "B", "C"]))
@click.option("--provider-id", default=None)
@click.option("--entry-kind", default=None, type=click.Choice(["direct_provider", "aggregator", "historical"]))
@click.pass_context
def research_entitlements(
    ctx: click.Context,
    eligibility_class: str | None,
    provider_id: str | None,
    entry_kind: str | None,
) -> None:
    """List October 2026 source-backed entitlement rows (machine catalogue)."""
    from privatemind.research.entitlements import list_entries, load_entitlements

    data = load_entitlements()
    rows = list_entries(
        data,
        eligibility_class=eligibility_class,
        provider_id=provider_id,
        entry_kind=entry_kind,
    )
    click.echo(
        json.dumps(
            {
                "schema_version": data.get("schema_version"),
                "retired": data.get("retired"),
                "count": len(rows),
                "entries": rows,
            },
            indent=2,
        )
    )


@research.command("github-sources")
@click.pass_context
def research_github_sources(ctx: click.Context) -> None:
    """List curated GitHub repos used for free-tier list recon."""
    from privatemind.research.github_lists import load_github_sources, raw_github_url

    meta = load_github_sources()
    sources = []
    for src in meta.get("sources", []):
        if not isinstance(src, dict):
            continue
        repo = str(src.get("repo") or "")
        path = str(src.get("path") or "README.md")
        branch = str(src.get("branch") or "main")
        sources.append(
            {
                "id": src.get("id"),
                "repo": repo,
                "raw_url": src.get("raw_url")
                or (raw_github_url(repo=repo, path=path, branch=branch) if repo else ""),
                "web_url": src.get("web_url"),
                "skip_fetch": bool(src.get("skip_fetch")),
                "notes": src.get("notes"),
            }
        )
    click.echo(json.dumps({"schema_version": meta.get("schema_version"), "sources": sources}, indent=2))


@research.command("discover")
@click.option("--source-id", default=None, help="Limit GitHub sync to one source id")
@click.option("--offline", is_flag=True, help="Skip network fetches")
@click.option("--write-report", is_flag=True, help="Write docs/data/free_tier_discovery_latest.json")
@click.option("--seed-gaps", is_flag=True, help="Log pending research candidates for catalog gaps")
@click.pass_context
def research_discover(
    ctx: click.Context,
    source_id: str | None,
    offline: bool,
    write_report: bool,
    seed_gaps: bool,
) -> None:
    """Search curated GitHub lists + hub collections; report gaps vs catalog/entitlements."""
    from privatemind.research.discover import run_discovery, write_latest_report
    from privatemind.research.candidates import log_candidate

    report = run_discovery(github_source_id=source_id, fetch_github=not offline)
    if write_report:
        path = write_latest_report(report)
        report["report_path"] = "docs/data/free_tier_discovery_latest.json"
    if seed_gaps:
        core = _core(ctx.obj["data_dir"], unlock_vault=False)
        seeded = []
        for row in report.get("gaps_from_github_lists") or []:
            pid = str(row.get("provider_id") or "")
            if not pid:
                continue
            slug = pid.replace("_", "-")
            log_candidate(
                core.memory,
                slug=slug,
                name=pid,
                category="llm",
                notes=str(row.get("probe_hint") or ""),
                verdict="pending",
            )
            seeded.append(slug)
        report["seeded_candidates"] = seeded
    click.echo(json.dumps(report, indent=2))


@research.command("github-sync")
@click.option("--source-id", default=None, help="Fetch only one source id from free_tier_github_sources.json")
@click.option("--offline", is_flag=True, help="Skip network; return empty scan (for tests)")
@click.pass_context
def research_github_sync(ctx: click.Context, source_id: str | None, offline: bool) -> None:
    """Fetch GitHub list READMEs and compare mentions to the provider catalog."""
    from privatemind.research.github_lists import sync_github_sources

    result = sync_github_sources(source_id=source_id, fetch=not offline)
    click.echo(json.dumps(result, indent=2))


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
