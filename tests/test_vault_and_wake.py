from pathlib import Path

import pytest

from privatemind.activation.readiness import ReadinessLevel, assess_readiness
from privatemind.config import Settings
from privatemind.core.agent import PrivateMindCore
from privatemind.vault.crypto import decrypt_payload, encrypt_payload
from privatemind.vault.store import AccountKind, CredentialVault


def test_vault_encrypt_roundtrip() -> None:
    payload = {"version": 1, "accounts": {"a": {"secrets": {"api_key": "x"}}}}
    token, meta = encrypt_payload("test-pass", payload)
    restored = decrypt_payload("test-pass", token, meta)
    assert restored["accounts"]["a"]["secrets"]["api_key"] == "x"


def test_readiness_requires_llm_and_github(tmp_path: Path) -> None:
    vault = CredentialVault(tmp_path)
    vault.initialize("test-pass")
    report = assess_readiness(vault)
    assert report.level == ReadinessLevel.DORMANT

    vault.add_account(
        passphrase="test-pass",
        name="primary",
        kind=AccountKind.LLM,
        public={"base_url": "https://example.com/v1", "model": "m"},
        secrets={"api_key": "k"},
    )
    partial = assess_readiness(vault)
    assert partial.level == ReadinessLevel.PARTIAL

    vault.add_account(
        passphrase="test-pass",
        name="agent-github",
        kind=AccountKind.GITHUB,
        public={"host": "github.com", "transport": "ssh"},
        secrets={"private_key": "-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n-----END OPENSSH PRIVATE KEY-----\n"},
    )
    alive = assess_readiness(vault)
    assert alive.level == ReadinessLevel.ALIVE


def test_public_summaries_never_include_secret_values(tmp_path: Path) -> None:
    vault = CredentialVault(tmp_path)
    vault.initialize("test-pass")
    vault.add_account(
        passphrase="test-pass",
        name="primary",
        kind=AccountKind.LLM,
        public={"base_url": "https://example.com/v1"},
        secrets={"api_key": "super-secret"},
    )
    summaries = vault.list_public_summaries()
    assert summaries[0]["secret_fields"] == ["api_key"]
    dumped = str(summaries)
    assert "super-secret" not in dumped


def test_wake_dormant_without_accounts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRIVATE_MIND_VAULT_PASSPHRASE", "test-pass")
    settings = Settings(data_dir=tmp_path)
    core = PrivateMindCore(settings=settings)
    core.vault.initialize("test-pass")
    core.unlock_vault("test-pass")
    outcome = core.wake.wake(run_health_checks=False)
    assert outcome["activated"] is False
    assert outcome["readiness"]["level"] == ReadinessLevel.DORMANT.value
