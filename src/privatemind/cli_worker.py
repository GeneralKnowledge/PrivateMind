import json
from pathlib import Path

import click

from privatemind.config import Settings
from privatemind.db import Database
from privatemind.worker.identity import NodeIdentity
from privatemind.worker.pairing_store import PairingStore


def _settings(data_dir: Path | None) -> Settings:
    return Settings() if not data_dir else Settings(data_dir=data_dir)


def _core_identity_path(settings: Settings) -> Path:
    return settings.data_dir / "core_identity.json"


def _worker_identity_path(settings: Settings) -> Path:
    return settings.data_dir / "worker_identity.json"


@click.group()
def worker_group() -> None:
    """Worker identity, pairing, leases, and local TCP service."""


@worker_group.command("init")
@click.option("--data-dir", type=click.Path(path_type=Path), default=None)
def worker_init(data_dir: Path | None) -> None:
    settings = _settings(data_dir)
    path = _worker_identity_path(settings)
    if path.exists():
        raise click.ClickException("Worker identity already exists")
    ident = NodeIdentity.generate("worker")
    ident.save(path)
    click.echo(json.dumps({"fingerprint": ident.fingerprint, "public_key_b64": ident.public_key_b64}, indent=2))


@worker_group.command("pair")
@click.argument("fingerprint")
@click.option("--public-key-b64", required=True)
@click.option("--label", default="")
@click.option("--host", "endpoint_host", default=None, help="Worker VM address for remote jobs")
@click.option("--port", "endpoint_port", default=None, type=int)
@click.option("--mtls/--no-mtls", default=False, help="Require mutual TLS to this worker")
@click.option("--data-dir", type=click.Path(path_type=Path), default=None)
def worker_pair(
    fingerprint: str,
    public_key_b64: str,
    label: str,
    endpoint_host: str | None,
    endpoint_port: int | None,
    mtls: bool,
    data_dir: Path | None,
) -> None:
    settings = _settings(data_dir)
    db = Database(settings.db_path)
    db.initialize()
    store = PairingStore(db)
    store.pair_worker(
        fingerprint=fingerprint,
        public_key_b64=public_key_b64,
        label=label,
        endpoint_host=endpoint_host,
        endpoint_port=endpoint_port,
        use_mtls=mtls,
    )
    click.echo(
        json.dumps(
            {
                "paired": fingerprint,
                "label": label,
                "endpoint_host": endpoint_host,
                "endpoint_port": endpoint_port,
                "use_mtls": mtls,
            }
        )
    )


@worker_group.command("lease")
@click.argument("worker_fingerprint")
@click.option("--operation", "operations", multiple=True, required=True)
@click.option("--lease-id", default=None)
@click.option("--max-jobs", type=int, default=None, help="Cap jobs charged against this lease (M5)")
@click.option("--expires-at", default=None, help="ISO8601 UTC expiry")
@click.option("--contributor-id", default=None, help="Scope lease to a registered contributor")
@click.option("--data-dir", type=click.Path(path_type=Path), default=None)
def worker_lease(
    worker_fingerprint: str,
    operations: tuple[str, ...],
    lease_id: str | None,
    max_jobs: int | None,
    expires_at: str | None,
    contributor_id: str | None,
    data_dir: Path | None,
) -> None:
    import uuid

    settings = _settings(data_dir)
    db = Database(settings.db_path)
    db.initialize()
    store = PairingStore(db)
    lid = lease_id or str(uuid.uuid4())
    limits = {"max_jobs": max_jobs} if max_jobs is not None else {}
    try:
        store.create_lease(
            lease_id=lid,
            worker_fingerprint=worker_fingerprint,
            operations=list(operations),
            limits=limits,
            expires_at=expires_at,
            contributor_id=contributor_id,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(
        json.dumps(
            {
                "lease_id": lid,
                "operations": list(operations),
                "limits": limits,
                "expires_at": expires_at,
                "contributor_id": contributor_id,
            }
        )
    )


@worker_group.group("contributor")
def worker_contributor_group() -> None:
    """Register contributors and assign workers (M5)."""


@worker_contributor_group.command("add")
@click.option("--name", "display_name", required=True)
@click.option("--contact", default="")
@click.option("--notes", default="")
@click.option("--contributor-id", default=None)
@click.option("--data-dir", type=click.Path(path_type=Path), default=None)
def worker_contributor_add(
    display_name: str,
    contact: str,
    notes: str,
    contributor_id: str | None,
    data_dir: Path | None,
) -> None:
    settings = _settings(data_dir)
    db = Database(settings.db_path)
    db.initialize()
    store = PairingStore(db)
    cid = store.add_contributor(
        display_name=display_name,
        contact=contact,
        notes=notes,
        contributor_id=contributor_id,
    )
    click.echo(json.dumps({"contributor_id": cid, "display_name": display_name}))


@worker_contributor_group.command("list")
@click.option("--data-dir", type=click.Path(path_type=Path), default=None)
def worker_contributor_list(data_dir: Path | None) -> None:
    settings = _settings(data_dir)
    db = Database(settings.db_path)
    db.initialize()
    store = PairingStore(db)
    click.echo(json.dumps({"contributors": store.list_contributors()}, indent=2))


@worker_contributor_group.command("assign")
@click.argument("worker_fingerprint")
@click.option("--contributor-id", required=True)
@click.option("--data-dir", type=click.Path(path_type=Path), default=None)
def worker_contributor_assign(worker_fingerprint: str, contributor_id: str, data_dir: Path | None) -> None:
    settings = _settings(data_dir)
    db = Database(settings.db_path)
    db.initialize()
    store = PairingStore(db)
    if not store.assign_worker_contributor(worker_fingerprint, contributor_id):
        raise click.ClickException("Worker or contributor not found")
    click.echo(json.dumps({"worker": worker_fingerprint, "contributor_id": contributor_id}))


@worker_group.group("trust")
def worker_trust_group() -> None:
    """Quarantine, restrict, and restore worker trust (M4)."""


@worker_trust_group.command("quarantine")
@click.argument("fingerprint")
@click.option("--data-dir", type=click.Path(path_type=Path), default=None)
def worker_trust_quarantine(fingerprint: str, data_dir: Path | None) -> None:
    settings = _settings(data_dir)
    db = Database(settings.db_path)
    db.initialize()
    store = PairingStore(db)
    if not store.quarantine_worker(fingerprint):
        raise click.ClickException("Worker not found")
    click.echo(json.dumps({"quarantined": fingerprint}))


@worker_trust_group.command("release")
@click.argument("fingerprint")
@click.option("--data-dir", type=click.Path(path_type=Path), default=None)
def worker_trust_release(fingerprint: str, data_dir: Path | None) -> None:
    settings = _settings(data_dir)
    db = Database(settings.db_path)
    db.initialize()
    store = PairingStore(db)
    if not store.release_quarantine(fingerprint):
        raise click.ClickException("Worker not found or not quarantined")
    click.echo(json.dumps({"released": fingerprint, "trust_state": "paired"}))


@worker_trust_group.command("restrict")
@click.argument("fingerprint")
@click.option("--data-dir", type=click.Path(path_type=Path), default=None)
def worker_trust_restrict(fingerprint: str, data_dir: Path | None) -> None:
    settings = _settings(data_dir)
    db = Database(settings.db_path)
    db.initialize()
    store = PairingStore(db)
    if not store.restrict_worker(fingerprint):
        raise click.ClickException("Worker not found")
    click.echo(json.dumps({"restricted": fingerprint}))


@worker_trust_group.command("restore")
@click.argument("fingerprint")
@click.option("--data-dir", type=click.Path(path_type=Path), default=None)
def worker_trust_restore(fingerprint: str, data_dir: Path | None) -> None:
    settings = _settings(data_dir)
    db = Database(settings.db_path)
    db.initialize()
    store = PairingStore(db)
    if not store.restore_paired(fingerprint):
        raise click.ClickException("Worker not found")
    click.echo(json.dumps({"trust_state": "paired", "fingerprint": fingerprint}))


@worker_trust_group.command("revoke")
@click.argument("fingerprint")
@click.option("--data-dir", type=click.Path(path_type=Path), default=None)
def worker_trust_revoke(fingerprint: str, data_dir: Path | None) -> None:
    settings = _settings(data_dir)
    db = Database(settings.db_path)
    db.initialize()
    store = PairingStore(db)
    if not store.revoke_worker(fingerprint):
        raise click.ClickException("Worker not found")
    click.echo(json.dumps({"revoked": fingerprint}))


@worker_group.command("list")
@click.option("--data-dir", type=click.Path(path_type=Path), default=None)
def worker_list(data_dir: Path | None) -> None:
    settings = _settings(data_dir)
    db = Database(settings.db_path)
    db.initialize()
    store = PairingStore(db)
    click.echo(json.dumps({"workers": store.list_workers()}, indent=2))


@worker_group.command("pki-init")
@click.option("--san", "sans", multiple=True, help="IP or DNS name for worker server cert SAN")
@click.option("--data-dir", type=click.Path(path_type=Path), default=None)
def worker_pki_init_cmd(sans: tuple[str, ...], data_dir: Path | None) -> None:
    from privatemind.worker.pki import init_dev_pki

    settings = _settings(data_dir)
    default_sans = list(sans) if sans else ["127.0.0.1", "localhost"]
    paths = init_dev_pki(settings.pki_dir, server_sans=default_sans)
    click.echo(json.dumps({k: str(v) for k, v in paths.items()}, indent=2))


@worker_group.command("serve")
@click.option("--host", default="127.0.0.1", help="Use 0.0.0.0 on a remote VM")
@click.option("--port", default=8765)
@click.option("--mtls/--no-mtls", default=None, help="Default: on if PKI files exist")
@click.option("--trusted-core", type=click.Path(exists=True, dir_okay=False, path_type=Path), default=None)
@click.option("--data-dir", type=click.Path(path_type=Path), default=None)
def worker_serve(
    host: str,
    port: int,
    mtls: bool | None,
    trusted_core: Path | None,
    data_dir: Path | None,
) -> None:
    from privatemind.worker.mtls import build_server_ssl_context, pki_ready, worker_server_paths
    from privatemind.worker.service import serve_worker
    from privatemind.worker.trusted_core import TrustedCore

    settings = _settings(data_dir)
    worker_path = _worker_identity_path(settings)
    if not worker_path.exists():
        raise click.ClickException("Run: privatemind worker init")
    worker = NodeIdentity.load(worker_path)

    core_fp: str
    core_pub: str
    trust_path = trusted_core or (settings.data_dir / "trusted_core.json")
    core_path = _core_identity_path(settings)
    if trust_path.is_file():
        tc = TrustedCore.load(trust_path)
        core_fp, core_pub = tc.fingerprint, tc.public_key_b64
    elif core_path.is_file():
        core = NodeIdentity.load(core_path)
        core_fp, core_pub = core.fingerprint, core.public_key_b64
    else:
        raise click.ClickException("Provide trusted_core.json (from brain: privatemind node export-trust)")

    use_mtls = mtls if mtls is not None else pki_ready(settings.pki_dir)
    ssl_ctx = None
    if use_mtls:
        if not pki_ready(settings.pki_dir):
            raise click.ClickException("mTLS enabled but PKI missing — run: privatemind worker pki init")
        ssl_ctx = build_server_ssl_context(worker_server_paths(settings.pki_dir))

    mode = "mTLS" if ssl_ctx else "plain TCP"
    click.echo(f"Worker {worker.fingerprint} listening on {host}:{port} ({mode})")
    serve_worker(
        host=host,
        port=port,
        identity=worker,
        core_fingerprint=core_fp,
        core_public_key_b64=core_pub,
        ssl_context=ssl_ctx,
    )


@worker_group.command("schedule")
@click.option("--text", default="privatemind-worker-m5")
@click.option("--contributor-id", default=None)
@click.option("--data-dir", type=click.Path(path_type=Path), default=None)
def worker_schedule(text: str, contributor_id: str | None, data_dir: Path | None) -> None:
    """Delegate compute_sha256 to the next schedulable worker (round-robin)."""
    from privatemind.core.agent import PrivateMindCore

    core = PrivateMindCore(settings=_settings(data_dir))
    if not core.worker_hub:
        raise click.ClickException("Core identity missing: privatemind node init")
    out = core.worker_hub.delegate_scheduled_compute_sha256(text, contributor_id=contributor_id)
    click.echo(json.dumps(out, indent=2))


@worker_group.command("demo")
@click.option("--text", default="privatemind-worker-m3")
@click.option("--schedule/--no-schedule", default=False, help="Use M5 scheduler instead of first worker")
@click.option("--data-dir", type=click.Path(path_type=Path), default=None)
def worker_demo(text: str, schedule: bool, data_dir: Path | None) -> None:
    """Delegate one compute_sha256 job to a paired local worker."""
    from privatemind.core.agent import PrivateMindCore

    core = PrivateMindCore(settings=_settings(data_dir))
    if not core.worker_hub:
        raise click.ClickException("Core identity missing: privatemind node init")
    if schedule:
        out = core.worker_hub.delegate_scheduled_compute_sha256(text)
    else:
        workers = core.pairing.list_workers()
        if not workers:
            raise click.ClickException("No paired workers")
        fp = workers[0]["fingerprint"]
        out = core.worker_hub.delegate_compute_sha256(text, worker_fingerprint=fp)
    click.echo(json.dumps(out, indent=2))
