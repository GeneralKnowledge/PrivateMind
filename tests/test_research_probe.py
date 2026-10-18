from unittest.mock import MagicMock, patch

from privatemind.db import Database
from privatemind.memory.store import MemoryStore
from privatemind.research.candidates import list_candidates, log_candidate
from privatemind.research.probe import probe_openai_compatible


def test_probe_openai_compatible_success() -> None:
    mock_resp = MagicMock()
    mock_resp.is_success = True
    mock_resp.status_code = 200
    mock_resp.text = '{"data":[{"id":"m1"}]}'
    mock_resp.json.return_value = {"data": [{"id": "m1"}, {"id": "m2"}]}
    with patch("privatemind.research.probe.httpx.get", return_value=mock_resp):
        out = probe_openai_compatible(base_url="https://example.com/v1", api_key="secret")
    assert out["ok"] is True
    assert out["model_count"] == 2


def test_log_and_list_candidates(tmp_path) -> None:
    db = Database(tmp_path / "r.sqlite3")
    db.initialize()
    mem = MemoryStore(db)
    log_candidate(
        mem,
        slug="nvidia-nim-hosted",
        name="NVIDIA NIM hosted",
        category="llm",
        verdict="useful",
        notes="probe ok",
    )
    rows = list_candidates(mem, verdict="useful")
    assert len(rows) == 1
    assert rows[0]["slug"] == "nvidia-nim-hosted"
