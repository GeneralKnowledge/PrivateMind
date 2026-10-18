import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from privatemind.vault.crypto import decrypt_payload, encrypt_payload


class AccountKind(str, Enum):
    LLM = "llm"
    GITHUB = "github"
    SSH_HOST = "ssh_host"


@dataclass
class AccountRecord:
    id: str
    name: str
    kind: AccountKind
    public: dict[str, Any]
    secrets: dict[str, str]
    created_at: str
    enabled: bool = True


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CredentialVault:
    """
    Encrypted account store (the agent's internal credential manager).
    Secrets never leave this module through list/summary APIs.
    """

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._vault_path = data_dir / "credentials.vault"
        self._meta_path = data_dir / "credentials.vault.meta"
        self._unlocked: dict[str, Any] | None = None

    @property
    def exists(self) -> bool:
        return self._vault_path.is_file() and self._meta_path.is_file()

    def is_unlocked(self) -> bool:
        return self._unlocked is not None

    def initialize(self, passphrase: str) -> None:
        if self.exists:
            raise FileExistsError("Vault already exists")
        payload = {"version": 1, "accounts": {}}
        token, meta = encrypt_payload(passphrase, payload)
        self._vault_path.write_bytes(token)
        self._meta_path.write_text(json.dumps(meta, indent=2))
        self._unlocked = payload

    def unlock(self, passphrase: str) -> None:
        if not self.exists:
            raise FileNotFoundError("Vault not initialized")
        meta = json.loads(self._meta_path.read_text())
        token = self._vault_path.read_bytes()
        self._unlocked = decrypt_payload(passphrase, token, meta)

    def lock(self) -> None:
        self._unlocked = None

    def _require_unlocked(self) -> dict[str, Any]:
        if self._unlocked is None:
            raise RuntimeError("Vault is locked")
        return self._unlocked

    def _persist(self, passphrase: str) -> None:
        payload = self._require_unlocked()
        token, meta = encrypt_payload(passphrase, payload)
        self._vault_path.write_bytes(token)
        self._meta_path.write_text(json.dumps(meta, indent=2))

    def add_account(
        self,
        *,
        passphrase: str,
        name: str,
        kind: AccountKind,
        public: dict[str, Any],
        secrets: dict[str, str],
    ) -> AccountRecord:
        vault = self._require_unlocked()
        account_id = str(uuid.uuid4())
        entry = {
            "id": account_id,
            "name": name,
            "kind": kind.value,
            "public": public,
            "secrets": secrets,
            "created_at": _utc_now(),
            "enabled": True,
        }
        vault.setdefault("accounts", {})[account_id] = entry
        self._persist(passphrase)
        return self._to_record(entry)

    def list_accounts(self, *, include_disabled: bool = False) -> list[AccountRecord]:
        vault = self._require_unlocked()
        records: list[AccountRecord] = []
        for entry in vault.get("accounts", {}).values():
            if not include_disabled and not entry.get("enabled", True):
                continue
            records.append(self._to_record(entry))
        records.sort(key=lambda r: (r.kind.value, r.name))
        return records

    def list_public_summaries(self) -> list[dict[str, Any]]:
        """Safe for display while locked is impossible — requires unlock."""
        return [
            {
                "id": r.id,
                "name": r.name,
                "kind": r.kind.value,
                "public": r.public,
                "enabled": r.enabled,
                "secret_fields": sorted(r.secrets.keys()),
            }
            for r in self.list_accounts(include_disabled=True)
        ]

    def get_account(self, account_id: str) -> AccountRecord | None:
        vault = self._require_unlocked()
        entry = vault.get("accounts", {}).get(account_id)
        return self._to_record(entry) if entry else None

    def get_by_name(self, name: str) -> AccountRecord | None:
        for record in self.list_accounts(include_disabled=True):
            if record.name == name:
                return record
        return None

    def set_enabled(self, account_id: str, enabled: bool, *, passphrase: str) -> None:
        vault = self._require_unlocked()
        entry = vault.get("accounts", {}).get(account_id)
        if not entry:
            raise KeyError(account_id)
        entry["enabled"] = enabled
        self._persist(passphrase)

    def delete_account(self, account_id: str, *, passphrase: str) -> None:
        vault = self._require_unlocked()
        if account_id not in vault.get("accounts", {}):
            raise KeyError(account_id)
        del vault["accounts"][account_id]
        self._persist(passphrase)

    @staticmethod
    def _to_record(entry: dict[str, Any]) -> AccountRecord:
        return AccountRecord(
            id=entry["id"],
            name=entry["name"],
            kind=AccountKind(entry["kind"]),
            public=entry.get("public", {}),
            secrets=entry.get("secrets", {}),
            created_at=entry.get("created_at", ""),
            enabled=bool(entry.get("enabled", True)),
        )
