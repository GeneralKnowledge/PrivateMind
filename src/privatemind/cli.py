import json
from pathlib import Path

import click

from privatemind.config import Settings
from privatemind.core.agent import PrivateMindCore


def _core(data_dir: Path | None) -> PrivateMindCore:
    settings = Settings()
    if data_dir:
        settings = Settings(data_dir=data_dir)
    return PrivateMindCore(settings=settings)


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
    core = _core(ctx.obj["data_dir"])
    click.echo(f"Initialized PrivateMind at {core.settings.db_path}")


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


@main.command("memory-search")
@click.option("--query", default=None)
@click.option("--kind", default=None)
@click.pass_context
def memory_search_cmd(ctx: click.Context, query: str | None, kind: str | None) -> None:
    core = _core(ctx.obj["data_dir"])
    rows = core.memory.search(query=query, kind=kind)
    click.echo(json.dumps(rows, indent=2))


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
