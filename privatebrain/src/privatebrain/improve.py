"""harness² as an optimizer: Propose–Probe–Compose over the brain's own past episodes.

It proposes a mind; it never adopts one. Its output goes through the same graded gate as GEPA's
(`experiment.Harness2Optimizer` -> `experiment.run_experiment`).

`BrainAdapter` is a harness² `BenchmarkAdapter` whose "benchmark" is the journal: each
replayable episode is a task, a domain is an area of the operator's work, and a rollout is
the episode re-run under a candidate mind. There is no grader; harness² compares runs
against each other, which is exactly the situation a personal agent is in.
"""

from __future__ import annotations

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


PROPOSER_WARNING = (
    "harness²'s proposer runs `claude --dangerously-skip-permissions`: the editing model gets an "
    "unrestricted shell as the operator's user. It works in a temporary copy of the mind, but "
    "nothing stops it reaching the brain home (FLOOR.md, state.json, approvals.jsonl) or anything "
    "else on the host. It is NOT sandboxed. Use it only attended, with --allow-unconfined."
)


@dataclass
class DirectClaudeProposer(Proposer):
    """harness²'s Proposer on the claude_cli channel, without forcing Vertex AI: it keeps the
    caller's own Anthropic credentials (API key or logged-in CLI). Refuses to exist unless the
    caller passes `unconfined_ok=True` (see PROPOSER_WARNING)."""

    unconfined_ok: bool = False

    def __post_init__(self) -> None:
        if not self.unconfined_ok:
            from .executor import UnconfinedRefused

            raise UnconfinedRefused(PROPOSER_WARNING)
        super().__post_init__()

    def env(self) -> dict[str, str]:
        e = dict(os.environ)
        e["ANTHROPIC_MODEL"] = self.spec.model
        return e


@dataclass
class ImproveResult:
    episode_id: str
    status: str
    tree: dict | None = None  # the mind harness² chose, when it differs from the live one
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
    """Run one harness² step on the latest replayable episode in `domain` and return the mind
    it selected. This only *proposes*: it never adopts. harness² selects without ground truth,
    so its choice is a candidate for the graded gate (`experiment.Harness2Optimizer`), which
    alone decides whether the live mind changes."""
    mind = adapter.mind
    episodes = adapter.journal.replayable(domain)
    if not episodes:
        return ImproveResult(episode_id="", status="no-episodes")
    ep = episodes[-1]
    token = mode_token(mode)
    tag = f"v{mind.version}"
    adapter.snapshot_base()
    lib = library_store.Library(root=adapter.home.library / f"k{k}", domain=domain, surface=SURFACE)
    res = run_task(
        ep.id,
        k,
        adapter=adapter,
        prop=proposer,
        runs_root=adapter.home.runs,
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
    work = Namespace(BENCH, SUBSTRATE, token, k, None, tag).task_dir(adapter.home.runs, ep.id)
    tree = harness_tree.read_tree(SURFACE, work / "harnesses" / sel["chosen_label"])
    if tree == mind.tree():
        out.status = "kept-current-mind"
        return out
    out.tree, out.status = tree, "candidate"
    return out
