import os


def resolve_passphrase(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    env = os.environ.get("PRIVATE_MIND_VAULT_PASSPHRASE")
    if env:
        return env
    raise RuntimeError(
        "Vault passphrase required. Set PRIVATE_MIND_VAULT_PASSPHRASE or pass --passphrase."
    )
