import ssl
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MtlsPaths:
    ca_cert: Path
    cert: Path
    key: Path


def core_client_paths(pki_dir: Path) -> MtlsPaths:
    return MtlsPaths(
        ca_cert=pki_dir / "ca.crt",
        cert=pki_dir / "core-client.crt",
        key=pki_dir / "core-client.key",
    )


def worker_server_paths(pki_dir: Path) -> MtlsPaths:
    return MtlsPaths(
        ca_cert=pki_dir / "ca.crt",
        cert=pki_dir / "worker-server.crt",
        key=pki_dir / "worker-server.key",
    )


def pki_ready(pki_dir: Path) -> bool:
    try:
        paths = core_client_paths(pki_dir)
        return paths.ca_cert.is_file() and paths.cert.is_file() and paths.key.is_file()
    except OSError:
        return False


def build_client_ssl_context(paths: MtlsPaths) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_verify_locations(cafile=str(paths.ca_cert))
    ctx.load_cert_chain(certfile=str(paths.cert), keyfile=str(paths.key))
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def build_server_ssl_context(paths: MtlsPaths) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_verify_locations(cafile=str(paths.ca_cert))
    ctx.load_cert_chain(certfile=str(paths.cert), keyfile=str(paths.key))
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx
