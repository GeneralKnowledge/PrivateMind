"""CLI: operational mode (slow_start / test / production)."""

from __future__ import annotations

import json
from pathlib import Path

import click

from privatemind.config import Settings
from privatemind.operational.mode import (
    operational_status,
    write_mode_state,
)


def _settings(data_dir: Path | None) -> Settings:
    if data_dir:
        return Settings(data_dir=data_dir)
    return Settings()


@click.group()
@click.pass_context
def mode_group(ctx: click.Context) -> None:
    """Slow start, test, and production throttles."""


@mode_group.command("status")
@click.pass_context
def mode_status(ctx: click.Context) -> None:
    """Show active mode and preset limits."""
    settings = _settings(ctx.obj.get("data_dir"))
    env_mode = settings.operational_mode if settings.operational_mode in ("slow_start", "test", "production") else None
    click.echo(json.dumps(operational_status(settings.data_dir, env_mode=env_mode), indent=2))


@mode_group.command("set")
@click.argument("name", type=click.Choice(["slow_start", "test", "production"]))
@click.option("--notes", default="", help="Optional note stored in operational_mode.json")
@click.pass_context
def mode_set(ctx: click.Context, name: str, notes: str) -> None:
    """Persist operational mode for this brain."""
    settings = _settings(ctx.obj.get("data_dir"))
    payload = write_mode_state(settings.data_dir, mode=name, notes=notes)
    click.echo(json.dumps({"saved": payload, "path": str(settings.data_dir / "operational_mode.json")}, indent=2))
