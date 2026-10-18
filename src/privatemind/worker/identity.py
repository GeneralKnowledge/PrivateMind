import base64
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


@dataclass
class NodeIdentity:
    role: str
    fingerprint: str
    private_key_b64: str
    public_key_b64: str

    @staticmethod
    def generate(role: str) -> "NodeIdentity":
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        priv_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        fp = fingerprint(pub_bytes)
        return NodeIdentity(
            role=role,
            fingerprint=fp,
            private_key_b64=base64.b64encode(priv_bytes).decode("ascii"),
            public_key_b64=base64.b64encode(pub_bytes).decode("ascii"),
        )

    def private_key(self) -> Ed25519PrivateKey:
        raw = base64.b64decode(self.private_key_b64)
        return Ed25519PrivateKey.from_private_bytes(raw)

    def public_key_bytes(self) -> bytes:
        return base64.b64decode(self.public_key_b64)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.__dict__, indent=2), encoding="utf-8")
        path.chmod(0o600)

    @staticmethod
    def load(path: Path) -> "NodeIdentity":
        data = json.loads(path.read_text(encoding="utf-8"))
        return NodeIdentity(**data)


def fingerprint(public_key_bytes: bytes) -> str:
    return hashlib.sha256(public_key_bytes).hexdigest()


def sign_message(private_key: Ed25519PrivateKey, message: bytes) -> str:
    sig = private_key.sign(message)
    return base64.b64encode(sig).decode("ascii")


def verify_message(public_key_bytes: bytes, message: bytes, signature_b64: str) -> bool:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature

    try:
        pub = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        pub.verify(base64.b64decode(signature_b64), message)
        return True
    except InvalidSignature:
        return False
