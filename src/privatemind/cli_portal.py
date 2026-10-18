"""CLI: local resource portal."""

from __future__ import annotations

import json
from pathlib import Path

import click

from privatemind.config import Settings
from privatemind.portal.config import load_portal_config
from privatemind.portal.intents import admin_note_path, list_donor_intents
from privatemind.portal.server import serve_portal


def _settings(data_dir: Path | None) -> Settings:
    if data_dir:
        return Settings(data_dir=data_dir)
    return Settings()


@click.group()
def portal_group() -> None:
    """Local HTTP portal — instructions and donor intents."""


@portal_group.command("serve")
@click.option("--host", default=None, help="Bind address (default from portal_config.json)")
@click.option("--port", default=None, type=int)
@click.option("--data-dir", type=click.Path(path_type=Path), default=None)
def portal_serve(host: str | None, port: int | None, data_dir: Path | None) -> None:
    """Serve instruction pages and donor intent API (stdlib HTTP)."""
    from privatemind.core.agent import PrivateMindCore

    settings = _settings(data_dir)
    cfg = load_portal_config()
    defaults = cfg.get("defaults") or {}
    bind_host = host or str(defaults.get("host") or "127.0.0.1")
    bind_port = port if port is not None else int(defaults.get("port") or 8780)

    core = PrivateMindCore(settings=settings)

    def status_provider() -> dict:
        from privatemind.operational.mode import operational_status

        report = core.wake.check()
        return {
            "readiness_level": report.get("level"),
            "ready": report.get("level") == "alive",
            "checks": report.get("checks"),
            "missing": report.get("missing"),
            "operational_mode": operational_status(
                settings.data_dir, env_mode=settings.operational_mode
            ).get("mode"),
        }

    click.echo(f"PrivateMind portal http://{bind_host}:{bind_port}/ (Ctrl+C to stop)")
    serve_portal(
        host=bind_host,
        port=bind_port,
        data_dir=settings.data_dir,
        status_provider=status_provider,
    )


@portal_group.command("intents")
@click.argument("action", type=click.Choice(["list"]))
@click.option("--data-dir", type=click.Path(path_type=Path), default=None)
def portal_intents(action: str, data_dir: Path | None) -> None:
    """List donor intents submitted via the portal."""
    settings = _settings(data_dir)
    if action == "list":
        click.echo(json.dumps({"intents": list_donor_intents(settings.data_dir)}, indent=2))


@portal_group.command("admin-note")
@click.option("--text", required=True)
@click.option("--data-dir", type=click.Path(path_type=Path), default=None)
def portal_admin_note(text: str, data_dir: Path | None) -> None:
    """Record a local admin note (first boot marker, not synced)."""
    settings = _settings(data_dir)
    path = admin_note_path(settings.data_dir)
    path.write_text(text.strip() + "\n", encoding="utf-8")
    click.echo(json.dumps({"written": str(path)}, indent=2))
