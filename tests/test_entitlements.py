from privatemind.research.entitlements import (
    category_a_provider_ids,
    list_entries,
    load_entitlements,
)


def test_entitlements_loads_and_has_categories() -> None:
    data = load_entitlements()
    assert data["schema_version"] == "2026-10-18"
    classes = {e["eligibility_class"] for e in data["entries"]}
    assert classes >= {"A", "B", "C"}


def test_category_a_includes_groq_not_sambanova() -> None:
    data = load_entitlements()
    a_ids = category_a_provider_ids(data)
    assert "groq" in a_ids
    assert "sambanova_cloud" not in a_ids


def test_retired_github_models() -> None:
    data = load_entitlements()
    retired = {r["provider_id"] for r in data.get("retired", [])}
    assert "github_models" in retired


def test_unorouter_is_aggregator_class_c() -> None:
    rows = list_entries(provider_id="unorouter")
    assert len(rows) == 1
    assert rows[0]["eligibility_class"] == "C"
    assert rows[0]["entry_kind"] == "aggregator"


def test_limits_have_official_and_enforced() -> None:
    for row in list_entries(eligibility_class="A"):
        assert "limits_official" in row
        assert "limits_enforced_conservative" in row
