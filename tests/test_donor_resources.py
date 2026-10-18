from privatemind.portal.intents import append_donor_intent
from privatemind.research.donor_resources import (
    load_donor_resource_catalog,
    valid_commitment_level_ids,
    valid_storage_backend_ids,
)


def test_catalog_has_traffic_and_r2() -> None:
    cat = load_donor_resource_catalog()
    levels = valid_commitment_level_ids(cat)
    assert "traffic_only" in levels
    assert "script_sandbox" in levels
    backends = valid_storage_backend_ids(cat)
    assert "cloudflare_r2" in backends
    assert "dropbox_free" in backends


def test_intent_with_resource_fields(tmp_path) -> None:
    rec = append_donor_intent(
        tmp_path,
        display_name="x",
        contact="c",
        offer="bronze",
        commitment_level="traffic_only",
        resource_kinds=["egress_bandwidth"],
        storage_backends=["cloudflare_r2"],
        paid_service_donation=False,
    )
    assert rec["commitment_level"] == "traffic_only"
    assert rec["resource_kinds"] == ["egress_bandwidth"]
