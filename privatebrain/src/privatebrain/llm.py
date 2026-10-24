"""Every model call goes through `call()`, which runs the Claude Code CLI with no tools and logs it.

No tools, no settings files, no MCP servers, no session persistence and an empty working
directory: the model can only read the prompt and write text back. That is the execution
side of the floor for experiments, and it is enforced here in code, not in the mind's text.

Each call is appended to a ledger with its purpose, the deterministic alternative that was
considered, the outcome and the cost, so unnecessary model use shows up in the records.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
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
    res = LLMResult(ok=False, text="", model=model, purpose=purpose, alternative=alternative)
    with tempfile.TemporaryDirectory(prefix="pb-llm-") as cwd:
        try:
            proc = subprocess.run(
                cmd, input=prompt, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            res.error = f"{type(exc).__name__}: {exc}"
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
                res.error = f"CLI error: {payload.get('subtype')} {str(payload.get('result'))[:300]}"
            elif proc.returncode != 0 and not payload:
                res.error = f"rc={proc.returncode}: {proc.stderr[-500:]}"
            else:
                res.ok, res.text = True, str(payload.get("result") or "")
    res.duration_s = round(time.monotonic() - t0, 2)
    if ledger is not None:
        append_jsonl(ledger, res.ledger_row())
    return res
