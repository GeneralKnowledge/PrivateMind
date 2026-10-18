"""Development PKI for mutual TLS between core and workers."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def _write_pem(path: Path, data: bytes, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(0o600 if private else 0o644)


def init_dev_pki(
    pki_dir: Path,
    *,
    common_name: str = "PrivateMind Dev CA",
    server_sans: list[str] | None = None,
) -> dict[str, Path]:
    """
    Create a small RSA CA and client/server certs for mTLS lab use.
    Production should use your org PKI or step-ca — not this long-term.
    """
    pki_dir.mkdir(parents=True, exist_ok=True)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    ca_subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.now(timezone.utc)
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_subject)
        .issuer_name(ca_subject)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=825))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(ca_key, hashes.SHA256())
    )

    ca_cert_path = pki_dir / "ca.crt"
    ca_key_path = pki_dir / "ca.key"
    _write_pem(
        ca_cert_path,
        ca_cert.public_bytes(serialization.Encoding.PEM),
    )
    _write_pem(
        ca_key_path,
        ca_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ),
        private=True,
    )

    sans = server_sans or ["localhost", "127.0.0.1"]
    paths: dict[str, Path] = {"ca_cert": ca_cert_path, "ca_key": ca_key_path}

    for role, fname in (("core-client", "core"), ("worker-server", "worker")):
        key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"privatemind-{fname}")])
        builder = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(ca_subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=825))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_encipherment=True,
                    content_commitment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
        )
        if role == "worker-server":
            import ipaddress

            alt_names: list[x509.GeneralName] = []
            for san in sans:
                try:
                    alt_names.append(x509.IPAddress(ipaddress.ip_address(san)))
                except ValueError:
                    alt_names.append(x509.DNSName(san))
            builder = builder.add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
        cert = builder.sign(ca_key, hashes.SHA256())
        cert_path = pki_dir / f"{role}.crt"
        key_path = pki_dir / f"{role}.key"
        _write_pem(cert_path, cert.public_bytes(serialization.Encoding.PEM))
        _write_pem(
            key_path,
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ),
            private=True,
        )
        paths[f"{fname}_cert"] = cert_path
        paths[f"{fname}_key"] = key_path

    return paths
