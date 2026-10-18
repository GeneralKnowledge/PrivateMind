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
@click.option("--data-dir", type=click.Path(path_type=Path), default=None)
def worker_pair(fingerprint: str, public_key_b64: str, label: str, data_dir: Path | None) -> None:
    settings = _settings(data_dir)
    db = Database(settings.db_path)
    db.initialize()
    store = PairingStore(db)
    store.pair_worker(fingerprint=fingerprint, public_key_b64=public_key_b64, label=label)
    click.echo(json.dumps({"paired": fingerprint, "label": label}))


@worker_group.command("lease")
@click.argument("worker_fingerprint")
@click.option("--operation", "operations", multiple=True, required=True)
@click.option("--lease-id", default=None)
@click.option("--data-dir", type=click.Path(path_type=Path), default=None)
def worker_lease(worker_fingerprint: str, operations: tuple[str, ...], lease_id: str | None, data_dir: Path | None) -> None:
    import uuid

    settings = _settings(data_dir)
    db = Database(settings.db_path)
    db.initialize()
    store = PairingStore(db)
    lid = lease_id or str(uuid.uuid4())
    store.create_lease(lease_id=lid, worker_fingerprint=worker_fingerprint, operations=list(operations))
    click.echo(json.dumps({"lease_id": lid, "operations": list(operations)}))


@worker_group.command("list")
@click.option("--data-dir", type=click.Path(path_type=Path), default=None)
def worker_list(data_dir: Path | None) -> None:
    settings = _settings(data_dir)
    db = Database(settings.db_path)
    db.initialize()
    store = PairingStore(db)
    click.echo(json.dumps({"workers": store.list_workers()}, indent=2))


@worker_group.command("serve")
@click.option("--host", default="127.0.0.1")
@click.option("--port", default=8765)
@click.option("--data-dir", type=click.Path(path_type=Path), default=None)
def worker_serve(host: str, port: int, data_dir: Path | None) -> None:
    from privatemind.worker.service import serve_worker

    settings = _settings(data_dir)
    worker_path = _worker_identity_path(settings)
    core_path = _core_identity_path(settings)
    if not worker_path.exists() or not core_path.exists():
        raise click.ClickException("Run: privatemind node init && privatemind worker init")
    worker = NodeIdentity.load(worker_path)
    core = NodeIdentity.load(core_path)
    click.echo(f"Worker {worker.fingerprint} listening on {host}:{port}")
    serve_worker(
        host=host,
        port=port,
        identity=worker,
        core_fingerprint=core.fingerprint,
        core_public_key_b64=core.public_key_b64,
    )


@worker_group.command("demo")
@click.option("--text", default="privatemind-worker-m3")
@click.option("--data-dir", type=click.Path(path_type=Path), default=None)
def worker_demo(text: str, data_dir: Path | None) -> None:
    """Delegate one compute_sha256 job to a paired local worker."""
    from privatemind.audit.log import AuditLog
    from privatemind.core.agent import PrivateMindCore

    core = PrivateMindCore(settings=_settings(data_dir))
    if not core.worker_hub:
        raise click.ClickException("Core identity missing: privatemind node init")
    workers = core.pairing.list_workers()
    if not workers:
        raise click.ClickException("No paired workers")
    fp = workers[0]["fingerprint"]
    out = core.worker_hub.delegate_compute_sha256(text, worker_fingerprint=fp)
    click.echo(json.dumps(out, indent=2))
