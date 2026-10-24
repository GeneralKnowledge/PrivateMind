"""The executive: one tick picks one activity — work, ask, improve, or reflect."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from harness2.core.proposer import Proposer

from .executor import Executor
from .home import Home
from .improve import BrainAdapter, default_channel, improve
from .journal import Episode, Journal
from .mind import Mind
from .needs import Needs, needs_from_deliverable

IMPROVE_EVERY = 3  # new replayable episodes in a domain before it is worth improving
BOREDOM_WINDOW = 3  # this many asks in a row and the brain does something else


@dataclass
class TickResult:
    activity: str
    detail: str


class Brain:
    def __init__(
        self,
        home: Home,
        executor: Executor,
        *,
        proposer_factory: Callable[[BrainAdapter], Proposer] | None = None,
        timeout: int = 1800,
        improve_k: int = 1,
    ):
        self.home = home
        self.executor = executor
        self.mind = Mind(home)
        self.journal = Journal(home)
        self.needs = Needs(home)
        self.proposer_factory = proposer_factory
        self.timeout = timeout
        self.improve_k = improve_k

    # --- the executive -----------------------------------------------------------------

    def tick(self) -> TickResult:
        self.mind.floor_text()  # refuses to run on a tampered floor
        state = self.home.load_state()
        if self.journal.queued():
            result = self.work()
        elif self._should_ask(state):
            asked = self.needs.request_batch(state)
            self.home.save_state(state)
            result = TickResult("ask", f"requested {len(asked)} need(s) in {self.home.requests}")
        elif (domain := self._domain_to_improve(state)) and self.proposer_factory:
            result = self.improve(domain)
        else:
            result = self.reflect()
        state = self.home.load_state()
        state["activities"] = (state["activities"] + [result.activity])[-20:]
        self.home.save_state(state)
        return result

    def _should_ask(self, state: dict) -> bool:
        if not self.needs.unmet() or self.needs.budget_left(state) <= 0:
            return False
        recent = state["activities"][-BOREDOM_WINDOW:]
        return not (len(recent) == BOREDOM_WINDOW and all(a == "ask" for a in recent))

    def _domain_to_improve(self, state: dict) -> str | None:
        counts = Counter(e.domain for e in self.journal.episodes() if e.replayable and e.ok)
        for domain, n in counts.most_common():
            if n - state["improved_at"].get(domain, 0) >= IMPROVE_EVERY:
                return domain
        return None

    # --- activities --------------------------------------------------------------------

    def work(self) -> TickResult:
        task = self.journal.pop()
        assert task is not None
        workdir = self.home.episodes / task.id
        tree = self.mind.tree()
        res = self.executor.run(
            task.prompt, self.mind.system_prompt(tree), tree, workdir, self.timeout
        )
        (workdir / "prompt.md").write_text(task.prompt, encoding="utf-8")
        self.journal.record(
            Episode(
                id=task.id,
                prompt=task.prompt,
                domain=task.domain,
                replayable=task.replayable,
                mind_version=self.mind.version,
                ok=res.ok,
                error=res.error,
            )
        )
        deliverable = workdir / "deliverable.md"
        found = needs_from_deliverable(deliverable.read_text(encoding="utf-8")) if res.ok else []
        for name, why in found:
            self.needs.add(name, why)
        detail = f"episode {task.id} {'ok' if res.ok else 'failed: ' + res.error[:200]}"
        if found:
            detail += f"; noticed {len(found)} need(s)"
        return TickResult("work", detail)

    def improve(self, domain: str) -> TickResult:
        adapter = BrainAdapter(self.home, self.executor, default_channel(), timeout=self.timeout)
        proposer = self.proposer_factory(adapter)
        out = improve(adapter, proposer, domain, k=self.improve_k)
        state = self.home.load_state()
        state["improved_at"][domain] = len(self.journal.replayable(domain))
        self.home.save_state(state)
        detail = f"{domain}: {out.status} on episode {out.episode_id}"
        if out.adopted_version is not None:
            detail += f" -> mind v{out.adopted_version}"
        if out.errors:
            detail += f" ({'; '.join(out.errors)[:300]})"
        return TickResult("improve", detail)

    def reflect(self) -> TickResult:
        state = self.home.load_state()
        eps = self.journal.episodes()
        needs = self.needs.all()
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        lines = [
            f"## Reflection — {stamp}",
            "",
            f"- mind: v{self.mind.version} (versions: {self.mind.versions()})",
            f"- episodes: {len(eps)} ({sum(e.ok for e in eps)} ok)",
            f"- needs: {dict(Counter(n.status for n in needs)) or 'none'}",
            f"- recent activity: {', '.join(state['activities'][-10:]) or 'none'}",
            "",
        ]
        with self.home.reflections.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return TickResult("reflect", f"wrote a note to {Path(self.home.reflections).name}")
