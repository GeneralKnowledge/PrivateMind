from pathlib import Path

import click

from privatemind.vault.passphrase import resolve_passphrase
from privatemind.vault.store import AccountKind, CredentialVault


def _vault(data_dir: Path | None) -> CredentialVault:
    from privatemind.config import Settings

    settings = Settings() if not data_dir else Settings(data_dir=data_dir)
    return CredentialVault(settings.data_dir)


def _unlock(vault: CredentialVault, passphrase: str | None) -> str:
    phrase = resolve_passphrase(passphrase)
    if not vault.exists:
        raise click.ClickException("Vault not initialized. Run: privatemind vault init")
    if not vault.is_unlocked():
        vault.unlock(phrase)
    return phrase


@click.group()
@click.pass_context
def vault_group(ctx: click.Context) -> None:
    """Encrypted credential vault (internal account manager)."""
    ctx.ensure_object(dict)


@vault_group.command("init")
@click.option("--passphrase", default=None, help="Or set PRIVATE_MIND_VAULT_PASSPHRASE")
@click.pass_context
def vault_init(ctx: click.Context, passphrase: str | None) -> None:
    vault = _vault(ctx.obj.get("data_dir"))
    if vault.exists:
        raise click.ClickException("Vault already exists")
    phrase = resolve_passphrase(passphrase)
    vault.initialize(phrase)
    click.echo("Vault initialized. Secrets are stored encrypted at credentials.vault")


@vault_group.command("status")
@click.pass_context
def vault_status(ctx: click.Context) -> None:
    import json

    vault = _vault(ctx.obj.get("data_dir"))
    click.echo(
        json.dumps(
            {
                "exists": vault.exists,
                "unlocked": vault.is_unlocked(),
                "path": str(vault._vault_path),  # noqa: SLF001 — operator diagnostics
            },
            indent=2,
        )
    )


@click.group()
@click.pass_context
def account_group(ctx: click.Context) -> None:
    """Register API, GitHub SSH, and server SSH accounts."""
    ctx.ensure_object(dict)


@account_group.command("list")
@click.option("--passphrase", default=None)
@click.pass_context
def account_list(ctx: click.Context, passphrase: str | None) -> None:
    vault = _vault(ctx.obj.get("data_dir"))
    phrase = _unlock(vault, passphrase)
    _ = phrase
    import json

    click.echo(json.dumps(vault.list_public_summaries(), indent=2))


@account_group.command("add-llm")
@click.option("--name", required=True, help="e.g. primary")
@click.option("--base-url", required=True)
@click.option("--api-key", default=None, help="Or prompt if omitted")
@click.option("--model", default="gpt-4o-mini")
@click.option("--passphrase", default=None)
@click.pass_context
def account_add_llm(
    ctx: click.Context,
    name: str,
    base_url: str,
    api_key: str | None,
    model: str,
    passphrase: str | None,
) -> None:
    vault = _vault(ctx.obj.get("data_dir"))
    phrase = _unlock(vault, passphrase)
    if not api_key:
        api_key = click.prompt("API key", hide_input=True)
    record = vault.add_account(
        passphrase=phrase,
        name=name,
        kind=AccountKind.LLM,
        public={"base_url": base_url, "model": model},
        secrets={"api_key": api_key},
    )
    click.echo(f"Added LLM account {record.name} ({record.id})")


@account_group.command("add-github")
@click.option("--name", required=True, help="e.g. agent-github")
@click.option("--host", default="github.com")
@click.option(
    "--private-key-file",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="SSH private key for the agent's dedicated GitHub user",
)
@click.option(
    "--probe-repo-ssh-url",
    default=None,
    help="Optional git@github.com:org/repo.git used during wake health check",
)
@click.option("--passphrase", default=None)
@click.pass_context
def account_add_github(
    ctx: click.Context,
    name: str,
    host: str,
    private_key_file: Path,
    probe_repo_ssh_url: str | None,
    passphrase: str | None,
) -> None:
    vault = _vault(ctx.obj.get("data_dir"))
    phrase = _unlock(vault, passphrase)
    private_key = private_key_file.read_text(encoding="utf-8")
    public = {"host": host, "transport": "ssh", "cli": "git+ssh"}
    if probe_repo_ssh_url:
        public["probe_repo_ssh_url"] = probe_repo_ssh_url
    record = vault.add_account(
        passphrase=phrase,
        name=name,
        kind=AccountKind.GITHUB,
        public=public,
        secrets={"private_key": private_key},
    )
    click.echo(f"Added GitHub SSH account {record.name} ({record.id})")


@account_group.command("add-ssh-host")
@click.option("--name", required=True, help="e.g. test-server")
@click.option("--host", required=True)
@click.option("--user", default="root")
@click.option("--port", default=22, show_default=True)
@click.option(
    "--private-key-file",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option("--no-wake-probe", is_flag=True, help="Skip SSH echo probe during wake")
@click.option("--passphrase", default=None)
@click.pass_context
def account_add_ssh_host(
    ctx: click.Context,
    name: str,
    host: str,
    user: str,
    port: int,
    private_key_file: Path,
    no_wake_probe: bool,
    passphrase: str | None,
) -> None:
    vault = _vault(ctx.obj.get("data_dir"))
    phrase = _unlock(vault, passphrase)
    private_key = private_key_file.read_text(encoding="utf-8")
    record = vault.add_account(
        passphrase=phrase,
        name=name,
        kind=AccountKind.SSH_HOST,
        public={
            "host": host,
            "user": user,
            "port": port,
            "transport": "ssh",
            "run_wake_probe": not no_wake_probe,
        },
        secrets={"private_key": private_key},
    )
    click.echo(f"Added SSH host account {record.name} ({record.id})")
