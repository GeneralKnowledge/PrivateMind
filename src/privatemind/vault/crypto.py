import base64
import json
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

VAULT_VERSION = 1
DEFAULT_KDF_ITERS = 480_000


def derive_key(passphrase: str, salt: bytes, iterations: int = DEFAULT_KDF_ITERS) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def encrypt_payload(passphrase: str, payload: dict[str, Any], *, salt: bytes | None = None) -> tuple[bytes, dict[str, Any]]:
    salt = salt or os.urandom(16)
    key = derive_key(passphrase, salt)
    token = Fernet(key).encrypt(json.dumps(payload).encode("utf-8"))
    meta = {
        "version": VAULT_VERSION,
        "salt": base64.b64encode(salt).decode("ascii"),
        "kdf_iters": DEFAULT_KDF_ITERS,
    }
    return token, meta


def decrypt_payload(passphrase: str, token: bytes, meta: dict[str, Any]) -> dict[str, Any]:
    salt = base64.b64decode(meta["salt"])
    iters = int(meta.get("kdf_iters", DEFAULT_KDF_ITERS))
    key = derive_key(passphrase, salt, iterations=iters)
    try:
        raw = Fernet(key).decrypt(token)
    except InvalidToken as exc:
        raise ValueError("Invalid vault passphrase or corrupted vault file") from exc
    return json.loads(raw.decode("utf-8"))
