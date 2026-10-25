"""The free OpenAI-compatible provider path in `llm.call`: offline, against a local stub server.

None of this is evidence about a real model; it checks the wiring, the boundary (no tools sent)
and that failures are charged to the right party.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from privatebrain import llm
from privatebrain.home import read_jsonl


class Stub:
    """A one-route chat-completions server that answers with a fixed status."""

    def __init__(self, status: int = 200, reply: str = "hello"):
        self.status, self.reply, self.requests = status, reply, []
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                stub.requests.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
                if stub.status == 200:
                    out = {"choices": [{"message": {"content": stub.reply}}],
                           "usage": {"prompt_tokens": 7, "completion_tokens": 2}}
                else:
                    out = {"error": {"message": "nope"}}
                data = json.dumps(out).encode()
                self.send_response(stub.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


@pytest.fixture
def stub(monkeypatch):
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    s = Stub()
    yield s
    s.server.shutdown()


def use(monkeypatch, provider: llm.Provider):
    monkeypatch.setattr(llm, "PROVIDER", provider)


def test_presets_and_overrides():
    assert not llm.provider_from_env({}).http
    p = llm.provider_from_env({"PRIVATEBRAIN_LLM_PROVIDER": "groq", "GROQ_API_KEY": "k"})
    assert (p.http, p.base_url, p.api_key, p.needs_key) == (True, "https://api.groq.com/openai/v1", "k", True)
    p = llm.provider_from_env({"PRIVATEBRAIN_LLM_PROVIDER": "ollama"})
    assert not p.needs_key and p.base_url.startswith("http://localhost")
    p = llm.provider_from_env({"PRIVATEBRAIN_LLM_PROVIDER": "openai_compat",
                               "PRIVATEBRAIN_LLM_BASE_URL": "https://x/v1/", "PRIVATEBRAIN_LLM_API_KEY": "k"})
    assert (p.base_url, p.api_key) == ("https://x/v1", "k")
    with pytest.raises(ValueError):
        llm.provider_from_env({"PRIVATEBRAIN_LLM_PROVIDER": "nonsense"})
    with pytest.raises(ValueError):
        llm.provider_from_env({"PRIVATEBRAIN_LLM_PROVIDER": "openai_compat"})


def test_http_call_sends_text_only_and_is_logged(monkeypatch, stub, tmp_path):
    use(monkeypatch, llm.Provider("groq", stub.url, "secret", needs_key=True))
    ledger = tmp_path / "llm_calls.jsonl"
    res = llm.call("hi", system="be brief", purpose="p", alternative="a", model="m", ledger=ledger)
    assert res.ok and res.text == "hello" and (res.input_tokens, res.output_tokens) == (7, 2)
    assert res.cost_usd == 0.0
    req = stub.requests[0]
    assert req["path"] == "/v1/chat/completions" and req["auth"] == "Bearer secret"
    # the boundary: a prompt in, text out; nothing the model could call
    assert set(req["body"]) == {"model", "temperature", "messages"}
    assert [r["status"] for r in read_jsonl(ledger)] == ["started", "finished"]
    assert "secret" not in ledger.read_text()


@pytest.mark.parametrize("status,kind", [(401, "auth"), (429, "provider"), (503, "provider"), (404, "rejected")])
def test_http_failures_are_charged_to_the_right_party(monkeypatch, stub, status, kind):
    stub.status = status
    use(monkeypatch, llm.Provider("groq", stub.url, "k", needs_key=True))
    res = llm.call("hi", system="", purpose="p", alternative="a", model="m")
    assert not res.ok and res.error_kind == kind


def test_missing_key_is_client_missing_and_sends_nothing(monkeypatch, stub):
    use(monkeypatch, llm.Provider("groq", stub.url, "", needs_key=True))
    res = llm.call("hi", system="", purpose="p", alternative="a", model="m")
    assert res.error_kind == "client_missing" and stub.requests == []


def test_unreachable_server_is_a_provider_failure(monkeypatch):
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    use(monkeypatch, llm.Provider("ollama", "http://127.0.0.1:9/v1", "", needs_key=False))
    res = llm.call("hi", system="", purpose="p", alternative="a", model="m", timeout=5)
    assert not res.ok and res.error_kind == "provider"
