"""Improve mode: harness² Propose–Probe–Compose over the brain's own past episodes.

`BrainAdapter` is a harness² `BenchmarkAdapter` whose "benchmark" is the journal: each
replayable episode is a task, a domain is an area of the operator's work, and a rollout is
the episode re-run under a candidate mind. There is no grader; harness² compares runs
against each other, which is exactly the situation a personal agent is in.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from harness2.core import library as library_store
from harness2.core import tree as harness_tree
from harness2.core.proposer import Proposer
from harness2.core.schedule import Namespace, mode_token, run_task
from harness2.core.spec import BenchPrompts, BenchSpec, ChannelSpec

from .executor import Executor
from .home import Home
from .journal import Journal
from .mind import SURFACE, Mind

SUBSTRATE = "pb"
BENCH = "privatebrain"

_FLOOR_OVERRIDE = re.compile(
    r"\b(ignore|override|disregard|bypass|suspend)\b[^.\n]{0,40}\bfloor\b", re.I
)


def default_channel() -> ChannelSpec:
    """The improver's channel: Claude Code, on the model named by PRIVATEBRAIN_IMPROVER_MODEL."""
    model = os.environ.get("PRIVATEBRAIN_IMPROVER_MODEL", "claude-opus-5-5")
    return ChannelSpec("claude_cli", model)


class BrainSubstrate:
    name = SUBSTRATE

    def surface(self):
        return SURFACE


class BrainAdapter:
    def __init__(
        self,
        home: Home,
        executor: Executor,
        channel: ChannelSpec,
        *,
        timeout: int = 1800,
    ):
        self.home = home
        self.mind = Mind(home)
        self.journal = Journal(home)
        self.executor = executor
        self.timeout = timeout
        self.substrate = BrainSubstrate()
        self.spec = BenchSpec(
            name=BENCH,
            runs_root=home.runs,
            install_mode="workspace_config",
            prompts=BenchPrompts(
                work="the operator's day-to-day tasks, done by a persistent personal agent",
                domain_word="area of work",
            ),
            channels={"proposer": channel, "selector": channel},
        )

    # --- what harness² asks of a benchmark ---------------------------------------------

    def tasks(self, split: str = "all") -> list[str]:
        return [e.id for e in self.journal.episodes() if e.replayable and e.ok]

    def domain_of(self, task_id: str) -> str:
        return self.journal.get(task_id).domain

    def task_prompt(self, task_id: str) -> str:
        return self.journal.get(task_id).prompt

    def task_files(self, task_id: str) -> Path | None:
        return None

    def base_harness(self) -> Path:
        return self.home.runs / "base_harness"

    def snapshot_base(self) -> None:
        """Freeze the live mind as the base every candidate is compared with."""
        shutil.rmtree(self.base_harness(), ignore_errors=True)
        harness_tree.write_tree(SURFACE, self.mind.tree(), self.base_harness(), stubs=False)

    def execute(
        self, task_id: str, harness_dir: Path | None, run_id: str, *, timeout: int | None = None
    ) -> Path:
        run_dir = self.home.runs / "exec" / run_id
        if (run_dir / "trajectory.md").is_file():
            return run_dir
        tree = harness_tree.read_tree(SURFACE, harness_dir or self.base_harness())
        res = self.executor.run(
            self.task_prompt(task_id),
            self.mind.system_prompt(tree),
            tree,
            run_dir,
            timeout or self.timeout,
        )
        if not res.ok:
            (run_dir / "error.txt").write_text(res.error, encoding="utf-8")
        return run_dir

    def delivered(self, run_dir: Path) -> bool:
        return (run_dir / "deliverable.md").is_file()

    def trajectory(self, run_dir: Path, *, obs_trunc: int) -> str:
        p = run_dir / "trajectory.md"
        return p.read_text(encoding="utf-8")[: obs_trunc * 4] if p.is_file() else ""

    def deliverable_text(self, run_dir: Path) -> str:
        p = run_dir / "deliverable.md"
        return p.read_text(encoding="utf-8") if p.is_file() else ""

    def deliverable_files(self, run_dir: Path) -> dict[str, str]:
        return {"deliverable.md": self.deliverable_text(run_dir)}

    def validate_tree(self, tree: dict[str, str]) -> None:
        """The floor's guard on the editable side: no component may talk the agent out of it."""
        bad = [rel for rel, text in tree.items() if _FLOOR_OVERRIDE.search(text)]
        if bad:
            raise ValueError(
                "these files tell the agent to set aside the operator's floor, which is not "
                f"editable and must stay in force: {', '.join(bad)}. Remove that wording."
            )

    def score(self, run_dir: Path, task_id: str) -> dict | None:
        return None


class DirectClaudeProposer(Proposer):
    """harness²'s Proposer on the claude_cli channel, without forcing Vertex AI: it keeps the
    caller's own Anthropic credentials (API key or logged-in CLI)."""

    def env(self) -> dict[str, str]:
        e = dict(os.environ)
        e["ANTHROPIC_MODEL"] = self.spec.model
        return e


@dataclass
class ImproveResult:
    episode_id: str
    status: str
    adopted_version: int | None = None
    pending: str = ""
    why: str = ""
    lesson: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def improve(
    adapter: BrainAdapter,
    proposer: Proposer,
    domain: str,
    *,
    k: int = 1,
    mode: str = "parallel",
    selector: Proposer | None = None,
) -> ImproveResult:
    """Run one harness² step on the latest replayable episode in `domain`, then adopt the
    selected mind if it differs from the live one AND came with an evidence-backed lesson."""
    home, mind = adapter.home, adapter.mind
    episodes = adapter.journal.replayable(domain)
    if not episodes:
        return ImproveResult(episode_id="", status="no-episodes")
    ep = episodes[-1]
    token = mode_token(mode)
    tag = f"v{mind.version}"
    adapter.snapshot_base()
    lib = library_store.Library(root=home.library / f"k{k}", domain=domain, surface=SURFACE)
    res = run_task(
        ep.id,
        k,
        adapter=adapter,
        prop=proposer,
        runs_root=home.runs,
        modes=(token,),
        tag=tag,
        library=lib,
        # Never let harness² build its own (Vertex-bound) selector behind our back.
        selector_prop=selector or proposer,
    )
    out = ImproveResult(episode_id=ep.id, status=res.status, errors=list(res.errors))
    sel = res.selections.get(token) or {}
    out.why, out.lesson = sel.get("why", ""), sel.get("experience") or {}
    if not sel.get("ok") or sel.get("chosen_tree_is_base", True):
        out.status = "kept-current-mind"
        return out
    if not library_store.has_experience(out.lesson):
        out.status = "no-evidence"
        return out

    work = Namespace(BENCH, SUBSTRATE, token, k, None, tag).task_dir(home.runs, ep.id)
    tree = harness_tree.read_tree(SURFACE, work / "harnesses" / sel["chosen_label"])
    if tree == mind.tree():
        out.status = "kept-current-mind"
        return out
    evidence = "\n".join(f"- {key}: {out.lesson[key]}" for key in out.lesson)
    source = f"harness2 {mode} k={k} on episode {ep.id} (from mind v{mind.version})"
    state = home.load_state()
    if state.get("auto_adopt", True):
        out.adopted_version = mind.adopt(tree, why=out.why, evidence=evidence, source=source)
        out.status = "adopted"
    else:
        pend = home.root / "pending" / ep.id
        harness_tree.write_tree(SURFACE, tree, pend / "harness", stubs=False)
        (pend / "proposal.json").write_text(
            json.dumps({"why": out.why, "evidence": evidence, "source": source}, indent=2),
            encoding="utf-8",
        )
        state["pending_adoptions"].append(ep.id)
        home.save_state(state)
        out.pending, out.status = str(pend), "pending-approval"
    return out


def approve_pending(home: Home, episode_id: str) -> int:
    pend = home.root / "pending" / episode_id
    meta = json.loads((pend / "proposal.json").read_text(encoding="utf-8"))
    tree = harness_tree.read_tree(SURFACE, pend / "harness")
    version = Mind(home).adopt(tree, **meta)
    state = home.load_state()
    state["pending_adoptions"] = [p for p in state["pending_adoptions"] if p != episode_id]
    home.save_state(state)
    shutil.rmtree(pend, ignore_errors=True)
    return version
