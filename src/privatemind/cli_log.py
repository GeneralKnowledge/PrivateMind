"""CLI: activity log (audit trail)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import click

from privatemind.activity.format import format_event_line
from privatemind.config import Settings
from privatemind.core.agent import PrivateMindCore


@click.command("log")
@click.option("--limit", default=40, show_default=True, help="Max events (newest first)")
@click.option("--category", default=None, help="Filter by audit category")
@click.option("--offset", default=0, show_default=True)
@click.option("--json", "as_json", is_flag=True, help="JSON array instead of lines")
@click.option("--follow", is_flag=True, help="Poll for new events (Ctrl+C to stop)")
@click.option("--interval", default=3.0, show_default=True, help="Poll seconds when --follow")
@click.option("--categories", is_flag=True, help="List known categories and exit")
@click.option("--data-dir", type=click.Path(path_type=Path), default=None, hidden=True)
@click.pass_context
def log_cmd(
    ctx: click.Context,
    limit: int,
    category: str | None,
    offset: int,
    as_json: bool,
    follow: bool,
    interval: float,
    categories: bool,
    data_dir: Path | None,
) -> None:
    """What the system has been doing (audit-backed activity log)."""
    dd = data_dir or ctx.obj.get("data_dir")
    core = _core(dd)
    if categories:
        click.echo(json.dumps({"categories": core.audit.list_categories()}, indent=2))
        return
    if follow:
        _follow(core, interval=interval, limit=min(limit, 50))
        return
    events = core.audit.list_events(limit=limit, category=category, offset=offset)
    if as_json:
        click.echo(json.dumps({"events": events, "limit": limit, "category": category}, indent=2))
        return
    if not events:
        click.echo("(no activity recorded yet — run wake, tick, or mode set)")
        return
    for ev in events:
        click.echo(format_event_line(ev))


def _follow(core: PrivateMindCore, *, interval: float, limit: int) -> None:
    seen: set[str] = set()
    click.echo(f"Following activity log (every {interval}s)...")
    try:
        while True:
            events = core.audit.list_events(limit=limit)
            for ev in reversed(events):
                eid = str(ev.get("id"))
                if eid in seen:
                    continue
                seen.add(eid)
                click.echo(format_event_line(ev))
            time.sleep(max(0.5, interval))
    except KeyboardInterrupt:
        click.echo("\nStopped.")


def _core(data_dir: Path | None) -> PrivateMindCore:
    settings = Settings(data_dir=data_dir) if data_dir else Settings()
    return PrivateMindCore(settings=settings)
