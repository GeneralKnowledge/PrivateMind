from privatemind.research.capability_domains import (
    capability_gaps,
    list_domains,
    load_capability_domains,
)


def test_load_domains_includes_email_and_wallet() -> None:
    data = load_capability_domains()
    ids = {d["id"] for d in list_domains(data)}
    assert "email_outbound" in ids
    assert "phone_sms" in ids
    assert "crypto_wallet" in ids
    assert "bank_fiat" in ids


def test_capability_gaps_without_vault_lists_email_as_missing() -> None:
    report = capability_gaps(None)
    missing_ids = {m["domain_id"] for m in report["missing_domains"]}
    assert "email_outbound" in missing_ids
    assert "phone_sms" in missing_ids
