"""Executors run one task under one mind. Everything the method needs lands in `workdir`:

- `trajectory.md` — what the agent did, in harness²'s [ACTION]/[OBSERVATION] grammar
- `deliverable.md` — what it produced
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from harness2.core import tree as harness_tree

from . import llm
from .mind import SURFACE


@dataclass
class ExecResult:
    ok: bool
    error: str = ""
    cost_usd: float = 0.0
    llm_calls: int = 0
    handled_by: str = "llm"


class Executor(Protocol):
    def run(
        self, prompt: str, system: str, tree: harness_tree.Tree, workdir: Path, timeout: int
    ) -> ExecResult: ...


def stage_tree(tree: harness_tree.Tree, workdir: Path) -> None:
    """Put the mind's on-demand parts (skills, scripts, subagents) where the agent can use
    them. Always-on files travel in the system prompt instead."""
    for rel, content in tree.items():
        if rel in SURFACE.always_on:
            continue
        p = workdir / harness_tree.normalize_rel(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


@dataclass
class FunctionExecutor:
    """Runs a Python callable as the agent. For tests and offline demos."""

    fn: Callable[[str, str, harness_tree.Tree, Path], str]

    def run(self, prompt, system, tree, workdir, timeout) -> ExecResult:
        workdir.mkdir(parents=True, exist_ok=True)
        stage_tree(tree, workdir)
        out = self.fn(prompt, system, tree, workdir)
        (workdir / "deliverable.md").write_text(out, encoding="utf-8")
        if not (workdir / "trajectory.md").exists():
            (workdir / "trajectory.md").write_text(
                f"[ACTION] answer the task\n[OBSERVATION]\n{out}\n", encoding="utf-8"
            )
        return ExecResult(ok=True)


# A fact about this execution environment, not part of the mind: the mind may have been
# written for an agent with tools, and without this note models narrate tool calls they
# cannot make (observed on the first real baseline, 2026-10-24).
NO_TOOLS_NOTE = (
    "\n\n# This run\n\nYou have no tools, files or network access in this run. Your reply "
    "itself is the deliverable: write it directly, with no tool calls.\n"
)


@dataclass
class SandboxedTextExecutor:
    """The experiment executor: one no-tools model call per task (see `llm.call`).

    Candidate minds run here, so nothing a candidate says can reach files, the network, the
    floor or credentials. Only the always-on part of the mind matters; skills and scripts
    need tools and are out of scope until a real sandbox exists.
    """

    model: str = field(default_factory=lambda: llm.EVAL_MODEL)
    ledger: Path | None = None
    purpose: str = "do the task under the given mind"
    alternative: str = "none: no deterministic capability matched this task"

    def run(self, prompt, system, tree, workdir, timeout) -> ExecResult:
        workdir.mkdir(parents=True, exist_ok=True)
        res = llm.call(
            prompt,
            system=system + NO_TOOLS_NOTE,
            purpose=self.purpose,
            alternative=self.alternative,
            model=self.model,
            timeout=timeout,
            ledger=self.ledger,
        )
        (workdir / "deliverable.md").write_text(res.text, encoding="utf-8")
        (workdir / "trajectory.md").write_text(
            f"[ACTION] answer the task ({res.model})\n[OBSERVATION]\n{res.text}\n", encoding="utf-8"
        )
        return ExecResult(ok=res.ok, error=res.error, cost_usd=res.cost_usd, llm_calls=1)


DEFAULT_ALLOWED_TOOLS = (
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "WebSearch",
    "WebFetch",
    "Bash(python3 scripts/*)",
)


@dataclass
class ClaudeCodeExecutor:
    """Runs the Claude Code CLI headless, with the mind as its appended system prompt.

    Credentials come from the environment (ANTHROPIC_API_KEY or a logged-in CLI).
    """

    model: str = os.environ.get("PRIVATEBRAIN_MODEL", "")
    allowed_tools: tuple[str, ...] = DEFAULT_ALLOWED_TOOLS
    cli: str = field(default_factory=lambda: shutil.which("claude") or "claude")

    def run(self, prompt, system, tree, workdir, timeout) -> ExecResult:
        workdir.mkdir(parents=True, exist_ok=True)
        stage_tree(tree, workdir)
        cmd = [
            self.cli,
            "-p",
            prompt,
            "--append-system-prompt",
            system,
            "--output-format",
            "stream-json",
            "--verbose",
            "--permission-mode",
            "acceptEdits",
            "--allowedTools",
            ",".join(self.allowed_tools),
        ]
        if self.model:
            cmd += ["--model", self.model]
        try:
            proc = subprocess.run(
                cmd, cwd=workdir, capture_output=True, text=True, timeout=timeout, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return ExecResult(ok=False, error=f"{type(exc).__name__}: {exc}")
        (workdir / "stream.jsonl").write_text(proc.stdout, encoding="utf-8")
        trajectory, final, cost = render_stream(proc.stdout)
        (workdir / "trajectory.md").write_text(trajectory, encoding="utf-8")
        deliverable = workdir / "deliverable.md"
        if not deliverable.is_file() and final:
            deliverable.write_text(final, encoding="utf-8")
        if proc.returncode != 0:
            return ExecResult(ok=False, error=proc.stderr[-2000:], cost_usd=cost)
        return ExecResult(ok=deliverable.is_file(), cost_usd=cost)


def render_stream(stdout: str, *, obs_trunc: int = 4000) -> tuple[str, str, float]:
    """Claude Code stream-json -> (trajectory text, final result text, cost in USD)."""
    lines: list[str] = []
    final, cost = "", 0.0
    for raw in stdout.splitlines():
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            continue
        kind = ev.get("type")
        if kind == "result":
            final = ev.get("result") or ""
            cost = float(ev.get("total_cost_usd") or 0.0)
            continue
        content = (ev.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            t = item.get("type")
            if t == "text" and kind == "assistant":
                lines.append(f"[THOUGHT] {item.get('text', '').strip()}")
            elif t == "tool_use":
                args = json.dumps(item.get("input", {}))[:400]
                lines.append(f"[ACTION] {item.get('name')} {args}")
            elif t == "tool_result":
                body = item.get("content")
                if isinstance(body, list):
                    body = "\n".join(str(b.get("text", "")) for b in body if isinstance(b, dict))
                lines.append(f"[OBSERVATION]\n{str(body)[:obs_trunc]}")
    if final:
        lines.append(f"[FINAL]\n{final}")
    return "\n".join(lines) + "\n", final, cost
