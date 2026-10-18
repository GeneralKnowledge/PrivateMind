import json
import threading
import urllib.error
import urllib.request
from http.client import HTTPConnection
from pathlib import Path

import pytest

from privatemind.portal.intents import append_donor_intent, list_donor_intents
from privatemind.portal.server import serve_portal


def test_append_and_list_donor_intents(tmp_path: Path) -> None:
    rec = append_donor_intent(
        tmp_path,
        display_name="Ada",
        contact="ada@example.com",
        offer="bronze",
        notes="ARM box",
    )
    assert rec["status"] == "pending"
    rows = list_donor_intents(tmp_path)
    assert len(rows) == 1
    assert rows[0]["display_name"] == "Ada"


def test_portal_http_status_and_intent(tmp_path: Path) -> None:
    port = 18780

    def status() -> dict:
        return {"readiness_level": "partial", "ready": False, "checks": [], "missing": ["llm"]}

    thread = threading.Thread(
        target=serve_portal,
        kwargs={"host": "127.0.0.1", "port": port, "data_dir": tmp_path, "status_provider": status},
        daemon=True,
    )
    thread.start()

    for _ in range(50):
        try:
            conn = HTTPConnection("127.0.0.1", port, timeout=0.5)
            conn.request("GET", "/api/v1/status")
            resp = conn.getresponse()
            if resp.status == 200:
                break
        except OSError:
            pass
    else:
        pytest.fail("portal did not start")

    conn = HTTPConnection("127.0.0.1", port, timeout=2)
    conn.request("GET", "/api/v1/status")
    body = json.loads(conn.getresponse().read().decode())
    assert body["readiness_level"] == "partial"
    assert "portal_version" in body

    payload = json.dumps(
        {"display_name": "Bob", "contact": "bob@test", "offer": "silver", "notes": ""}
    ).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/v1/donor/intent",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=2) as post_resp:
        assert post_resp.status == 201
    assert len(list_donor_intents(tmp_path)) == 1
