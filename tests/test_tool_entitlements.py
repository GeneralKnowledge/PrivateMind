from unittest.mock import MagicMock, patch

from privatemind.research.probe import probe_brave_web_search
from privatemind.research.tool_entitlements import list_tool_entries, load_tool_entitlements


def test_tool_entitlements_has_brave_and_openserp() -> None:
    data = load_tool_entitlements()
    ids = {e["provider_id"] for e in data["entries"]}
    assert "brave_search" in ids
    assert "brave_answers" in ids
    assert "openserp" in ids


def test_brave_answers_instant_answer_kind() -> None:
    rows = list_tool_entries(provider_id="brave_answers")
    assert rows[0]["tool_kind"] == "instant_answer"


def test_probe_brave_web_search_success() -> None:
    mock_resp = MagicMock()
    mock_resp.is_success = True
    mock_resp.status_code = 200
    mock_resp.text = '{"web":{"results":[{"title":"T"}]}}'
    mock_resp.json.return_value = {"web": {"results": [{"title": "T"}]}}
    with patch("privatemind.research.probe.httpx.get", return_value=mock_resp):
        out = probe_brave_web_search(api_key="secret")
    assert out["ok"] is True
    assert out.get("sample_title") == "T"
