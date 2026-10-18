from unittest.mock import patch

from privatemind.research.discover import run_discovery, write_latest_report


def test_run_discovery_offline(tmp_path) -> None:
    with patch("privatemind.research.discover.sync_github_sources") as mock_sync:
        mock_sync.return_value = {
            "mentioned_provider_ids": ["groq"],
            "retired_mentions_in_lists": ["github_models"],
            "in_github_lists_not_in_catalog": ["cerebras"],
            "errors": {},
        }
        with patch("privatemind.research.discover.fetch_url_text") as mock_fetch:
            mock_fetch.return_value = "**Typhoon (SCB 10X)** free API"
            report = run_discovery(fetch_github=False)
    assert "category_a_provider_ids" in report
    assert any(g["provider_id"] == "cerebras" for g in report["gaps_from_github_lists"])
    assert "pacocartones-always-free" in report.get("hub_collections", {})


def test_write_latest_report(tmp_path) -> None:
    p = write_latest_report({"generated_at": "2026-10-18T00:00:00+00:00", "ok": True}, path=tmp_path / "r.json")
    assert p.exists()
