"""Every model call goes through `call()`, which runs the Claude Code CLI with no tools and logs it.

No tools, no settings files, no MCP servers, no session persistence and an empty working
directory: the model can only read the prompt and write text back. That is the execution
side of the floor for experiments, and it is enforced here in code, not in the mind's text.

Each call is appended to a ledger with its purpose, the deterministic alternative that was
considered, the outcome and the cost, so unnecessary model use shows up in the records. A row
with `status: "started"` is written *before* the call, so a call killed mid-flight still leaves
a trace; its cost is unknown, and budget checks charge it at its cap (`max_budget_usd`).

A failure carries an `error_kind`, so the caller can tell whose fault it was:

| error_kind | meaning | what the substrate does |
|---|---|---|
| client_missing | the `claude` CLI is not installed or not runnable | wait for the model; not the job's fault |
| auth | the provider rejected the credentials (401/403) | breaker; wait; not the job's fault |
| provider | rate limited, overloaded or a server error (429/5xx) | breaker; wait; not the job's fault |
| rejected | the provider refused this request (other 4xx, e.g. unknown model) | counts against the job |
| timeout | no reply within the time limit | counts against the job |
| unknown | anything else | counts against the job |
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .home import append_jsonl

EVAL_MODEL = os.environ.get("PRIVATEBRAIN_EVAL_MODEL", "claude-haiku-5-5")
IMPROVER_MODEL = os.environ.get("PRIVATEBRAIN_IMPROVER_MODEL", "claude-opus-5-5")


@dataclass
class LLMResult:
    ok: bool
    text: str
    model: str
    purpose: str
    alternative: str
    cost_usd: float = 0.0
    duration_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    error: str = ""
    error_kind: str = ""
    call_id: str = ""
    max_budget_usd: float = 0.0
    status: str = "finished"
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    def ledger_row(self) -> dict:
        row = asdict(self)
        row.pop("text")
        return row


def call(
    prompt: str,
    *,
    system: str,
    purpose: str,
    alternative: str,
    model: str = EVAL_MODEL,
    timeout: int = 300,
    max_budget_usd: float = 1.0,
    ledger: Path | None = None,
) -> LLMResult:
    """One sandboxed, logged model call. `purpose` says why a model is needed at all;
    `alternative` names the deterministic route that was considered and why it was not used."""
    cli = shutil.which("claude") or "claude"
    cmd = [
        cli,
        "-p",
        "--output-format",
        "json",
        "--model",
        model,
        "--system-prompt",
        system,
        "--tools",
        "",
        "--setting-sources",
        "",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--max-budget-usd",
        str(max_budget_usd),
    ]
    t0 = time.monotonic()
    res = LLMResult(ok=False, text="", model=model, purpose=purpose, alternative=alternative,
                    call_id=uuid.uuid4().hex[:12], max_budget_usd=max_budget_usd)
    if ledger is not None:
        append_jsonl(ledger, {**res.ledger_row(), "status": "started", "cost_usd": None})
    with tempfile.TemporaryDirectory(prefix="pb-llm-") as cwd:
        try:
            proc = subprocess.run(
                cmd, input=prompt, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
            )
        except FileNotFoundError as exc:
            res.error, res.error_kind = f"model client not found: {exc}", "client_missing"
        except subprocess.TimeoutExpired as exc:
            res.error, res.error_kind = f"TimeoutExpired: {exc}", "timeout"
        except OSError as exc:
            res.error, res.error_kind = f"{type(exc).__name__}: {exc}", "client_missing"
        else:
            try:
                payload = json.loads(proc.stdout)
            except json.JSONDecodeError:
                payload = {}
            res.cost_usd = float(payload.get("total_cost_usd") or 0.0)
            usage = payload.get("usage") or {}
            res.input_tokens = int(
                (usage.get("input_tokens") or 0)
                + (usage.get("cache_read_input_tokens") or 0)
                + (usage.get("cache_creation_input_tokens") or 0)
            )
            res.output_tokens = int(usage.get("output_tokens") or 0)
            if payload.get("is_error") or payload.get("subtype") not in (None, "success"):
                res.error = (f"CLI error: {payload.get('subtype')} status={payload.get('api_error_status')} "
                             f"{str(payload.get('result'))[:300]}")
                res.error_kind = classify(payload.get("api_error_status"), res.error)
            elif proc.returncode != 0 and not payload:
                res.error = f"rc={proc.returncode}: {proc.stderr[-500:]}"
                res.error_kind = classify(None, res.error)
            else:
                res.ok, res.text = True, str(payload.get("result") or "")
    res.duration_s = round(time.monotonic() - t0, 2)
    if ledger is not None:
        append_jsonl(ledger, res.ledger_row())
    return res


# Phrases the CLI uses when it cannot authenticate; a status code is preferred when present.
_AUTH_TEXT = ("invalid api key", "not logged in", "please run /login", "authentication", "unauthorized",
              "oauth token", "credit balance is too low")
_PROVIDER_TEXT = ("overloaded", "rate limit", "rate_limit", "internal server error", "service unavailable",
                  "bad gateway", "econnreset", "econnrefused", "etimedout", "socket hang up", "fetch failed",
                  "connection error", "unable to connect")


def classify(status, error: str) -> str:
    """Whose failure is this? See the table in the module docstring."""
    try:
        code = int(status) if status is not None else None
    except (TypeError, ValueError):
        code = None
    text = error.lower()
    if code in (401, 403) or (code is None and any(t in text for t in _AUTH_TEXT)):
        return "auth"
    if code is not None and (code == 429 or code >= 500):
        return "provider"
    if code is not None and 400 <= code < 500:
        return "rejected"
    if any(t in text for t in _PROVIDER_TEXT):
        return "provider"
    return "unknown"


def unfinished_calls(ledger: Path) -> list[dict]:
    """Calls with a `started` row and no finished row: killed mid-flight, cost unknown."""
    from .home import read_jsonl_tolerant

    rows, _ = read_jsonl_tolerant(ledger)
    done = {r.get("call_id") for r in rows if r.get("status", "finished") != "started"}
    return [r for r in rows if r.get("status") == "started" and r.get("call_id") not in done]
