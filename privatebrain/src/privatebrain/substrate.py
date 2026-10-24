"""The substrate: a persistent loop that keeps the brain alive, coherent and useful with no
model available. Levels 1 and 2 of the layered design; models plug in above it.

Each tick, in order:

1. **Floor** (level 1). A tampered floor halts all work; the loop keeps sensing and beating.
2. **Inbox.** Tasks queued with `privatebrain task` become jobs with a state.
3. **Senses.** Clock, process and resources, connectivity; events on change (`senses.py`).
4. **Reconcile.** A waiting or blocked job whose prerequisite is back returns to the queue;
   model work is parked when the remote model goes away.
5. **One job.** Routed by ordinary rules: a registry capability, a pure compute route, a memory
   lookup, or work that needs the remote model. Safety checks run first (`safety.py`). The job
   is marked running and saved *before* it runs, so a crash is noticed and recovered.
6. **Vitals.** The whole reading, the job counts and a heartbeat go to `vitals.json`.

Job states: queued -> running -> done | failed, or waiting (needs something that will come
back: the remote model, budget, storage) or blocked (needs someone: an approval, a missing
capability). "Waiting" means *I cannot do this right now*; a failure of kind `unknown` means
*I do not know how*.

Only this loop writes `jobs.json`, `substrate.json` and `vitals.json`; a lock file with its pid
keeps a second loop out and tells the next start whether the last one died.
"""

from __future__ import annotations

import json
import os
import signal
import time
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import llm, recall, safety
from .capabilities import PURE_ROUTES, REGISTRY, CapabilityError, ComputeFirstExecutor, budget_route_applies
from .events import EventLog, event, now_iso
from .executor import Executor, SandboxedTextExecutor
from .home import Home, read_jsonl, write_json
from .journal import Episode, Journal, new_id
from .mind import Mind
from .needs import Needs, slug
from .senses import Probes, Senses

MAX_ATTEMPTS = 3
BACKOFF_S = 30  # first retry delay; doubles each attempt
BREAKER_FAILURES = 3  # consecutive failed model calls before the breaker opens
BREAKER_COOLDOWN_S = 300
TERMINAL = ("done", "failed")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(ts: str) -> datetime | None:
    if not ts:
        return None
    d = datetime.fromisoformat(ts)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


@dataclass
class Job:
    id: str
    prompt: str = ""
    capability: str = ""
    args: dict = field(default_factory=dict)
    domain: str = "general"
    replayable: bool = True
    requires: list = field(default_factory=list)
    deadline: str = ""
    not_before: str = ""
    every_s: int = 0
    origin: str = "operator"
    state: str = "queued"
    route: str = ""
    needs: list = field(default_factory=list)  # resources the route depends on, e.g. remote_model
    waiting_for: list = field(default_factory=list)
    reason: str = ""
    attempts: int = 0
    interrupted: bool = False
    overdue_reported: bool = False
    created: str = ""
    updated: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Job":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})


def plan(job: Job) -> tuple[str, list[str]]:
    """(route, needs) by ordinary rules. No model is asked how to route."""
    if job.capability:
        return (f"capability:{job.capability}", []) if job.capability in REGISTRY else ("unknown", [])
    if recall.recall_query(job.prompt):
        return "recall", []
    for route in PURE_ROUTES:
        if route(job.prompt) is not None:
            return f"pure:{route.__name__}", []
    if budget_route_applies(job.prompt):
        return "mixed:budget_route", ["remote_model"]
    return "model", ["remote_model"]


class AlreadyRunning(RuntimeError):
    pass


@dataclass
class Outcome:
    status: str  # done | retry | failed | waiting
    deliverable: str = ""
    detail: dict = field(default_factory=dict)
    kind: str = ""  # why it failed or waits
    error: str = ""


class Substrate:
    def __init__(
        self,
        home: Home,
        *,
        executor: Executor | None = None,
        probes: Probes | None = None,
        forced_offline: bool = False,
        probe_every_s: float = 30.0,
        model: str = llm.EVAL_MODEL,
        budget_usd: float = safety.DAILY_MODEL_BUDGET_USD,
        timeout: int = 300,
    ):
        self.home = home
        ledger = home.root / "llm_calls.jsonl"
        # Model work runs with no tools (llm.call): the substrate does not hand a model the host.
        self.executor = executor or ComputeFirstExecutor(
            SandboxedTextExecutor(model=model, ledger=ledger), model=model, ledger=ledger)
        self.senses = Senses(home, probes or Probes(), probe_every_s=probe_every_s,
                             forced_offline=forced_offline)
        self.events = EventLog(home)
        self.journal = Journal(home)
        self.needs = Needs(home)
        self.mind = Mind(home)
        self.budget_usd = budget_usd
        self.timeout = timeout
        self.jobs_file = home.root / "jobs.json"
        self.state_file = home.root / "substrate.json"
        self.vitals_file = home.root / "vitals.json"
        self.lock_file = home.root / "substrate.lock"
        self.jobs: list[Job] = [Job.from_dict(d) for d in self._read(self.jobs_file, [])]
        self.state: dict = {"breaker": {"failures": 0, "opened_at": ""}, "halted": "", "ticks": 0,
                            **self._read(self.state_file, {})}
        self.vitals: dict = self._read(self.vitals_file, {})
        self._stop = False
        self._started = False

    # --- persistence -----------------------------------------------------------------------------

    @staticmethod
    def _read(path: Path, default):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return default

    def _save(self) -> None:
        write_json(self.jobs_file, [asdict(j) for j in self.jobs])
        write_json(self.state_file, self.state)

    def emit(self, type: str, **kw) -> dict:
        return self.events.emit(event(type, **{"source": "substrate", **kw}))

    def _set(self, job: Job, state: str, *, reason: str = "", waiting_for=(), **ev) -> None:
        job.state, job.reason, job.waiting_for, job.updated = state, reason, list(waiting_for), now_iso()
        self._save()
        sev = {"failed": "warning", "blocked": "warning"}.get(state, "info")
        self.emit(f"task_{state}", severity=sev, task=job.id, route=job.route,
                  **({"reason": reason} if reason else {}),
                  **({"waiting_for": list(waiting_for)} if waiting_for else {}), **ev)

    # --- lifecycle -------------------------------------------------------------------------------

    def start(self) -> None:
        """Take the lock and recover from whatever the last run left behind."""
        self.home.root.mkdir(parents=True, exist_ok=True)
        prev_pid = None
        try:
            prev_pid = int(self.lock_file.read_text().strip())
        except (OSError, ValueError):
            pass
        if prev_pid and prev_pid != os.getpid() and _alive(prev_pid):
            raise AlreadyRunning(f"a substrate loop is already running (pid {prev_pid})")
        self.lock_file.write_text(str(os.getpid()))
        if prev_pid:
            self.emit("crash_recovered", severity="warning", previous_pid=prev_pid,
                      last_heartbeat=self.vitals.get("heartbeat", ""))
        for job in self.jobs:
            if job.state != "running":
                continue
            job.interrupted = True
            if job.attempts >= MAX_ATTEMPTS:
                self._set(job, "failed", reason=f"interrupted {job.attempts} times", kind="crashed")
            elif not job.replayable and job.id not in safety.approvals(self.home):
                # It may already have acted on the world: tell the operator now, do not retry.
                self._set(job, "blocked", reason="interrupted during a run that acts on the world; check "
                          f"whether it happened, then `privatebrain approve {job.id}` to retry",
                          waiting_for=["approval"], kind="crashed", recovered=True)
            else:
                self._set(job, "queued", reason="interrupted by a crash; requeued", recovered=True)
        self._started = True
        self.emit("started", pid=os.getpid(), jobs=len(self.jobs))

    def stop(self) -> None:
        if not self._started:
            return
        self._save()
        self.emit("stopped", pid=os.getpid(), ticks=self.state["ticks"])
        try:
            if self.lock_file.read_text().strip() == str(os.getpid()):
                self.lock_file.unlink()
        except OSError:
            pass
        self._started = False

    def run(self, *, max_ticks: int | None = None, interval: float = 2.0, until_idle: bool = False) -> None:
        def handle(signum, _frame):
            self._stop = True

        old = {s: signal.signal(s, handle) for s in (signal.SIGTERM, signal.SIGINT)}
        self.start()
        try:
            n = 0
            while not self._stop and (max_ticks is None or n < max_ticks):
                did = self.tick()
                n += 1
                if until_idle and not did and not self._runnable():
                    break
                if not did:
                    time.sleep(interval)
        finally:
            self.stop()
            for s, h in old.items():
                signal.signal(s, h)

    # --- one tick --------------------------------------------------------------------------------

    def tick(self) -> bool:
        """One pass. Returns True if a job ran."""
        if not self._started:
            self.start()
        self.state["ticks"] += 1
        problem = safety.floor_problem(self.home)
        if problem:
            if not self.state["halted"]:
                self.emit("floor_tampered", severity="critical", detail=problem)
            self.state["halted"] = problem
            self._write_vitals(self.vitals)
            return False
        if self.state["halted"]:
            self.emit("floor_restored")
            self.state["halted"] = ""

        self._ingest()
        reading, evs = self.senses.read(self.vitals, breaker_open=self._breaker_open())
        for ev in evs:
            self.events.emit(ev)
        self.vitals = reading
        self._temporal()
        self._reconcile()
        self._write_vitals(self.vitals)  # a heartbeat before any work that could hang or crash
        job = self._next()
        if job is None:
            return False
        self._dispatch(job)
        self._write_vitals(self.vitals)
        return True

    def _ingest(self) -> None:
        while (t := self.journal.pop()) is not None:
            job = Job.from_dict({**asdict(t), "created": now_iso(), "updated": now_iso()})
            job.route, job.needs = plan(job)
            self.jobs.append(job)
            self._save()
            self.emit("task_received", task=job.id, route=job.route, needs=job.needs, origin=job.origin)

    def propose(self, proposal: dict) -> Job:
        """The way a higher level asks for work: validated, and never with operator authority."""
        fields_ = safety.validate_proposal(proposal)
        t = self.journal.enqueue(fields_.pop("prompt", ""), **fields_)
        self.emit("task_proposed", task=t.id, origin="model")
        return Job.from_dict(asdict(t))

    def _temporal(self) -> None:
        now = _now()
        for job in self.jobs:
            dl = _parse(job.deadline)
            if dl and dl < now and job.state not in TERMINAL and not job.overdue_reported:
                job.overdue_reported = True
                self._save()
                self.emit("task_overdue", severity="warning", task=job.id, deadline=job.deadline,
                          state=job.state)

    def _available(self, resource: str, job: Job | None = None) -> bool:
        if resource == "approval":
            return job is not None and job.id in safety.approvals(self.home)
        if resource.startswith("need:"):
            return resource[5:] in {n.name for n in self.needs.all() if n.status == "satisfied"}
        if resource == "remote_model":
            return bool(self.vitals.get("connectivity", {}).get("remote_model"))
        if resource == "model_budget":
            return safety.spent_today(self.home) < self.budget_usd
        if resource == "storage":
            return bool(self.vitals.get("internal", {}).get("storage_writable"))
        return False

    def _reconcile(self) -> None:
        """Park model work while the model is away; return parked or blocked work whose
        prerequisites are back. Bounded and idempotent: it only moves jobs between states."""
        online = self._available("remote_model")
        parked, resumed = [], []
        for job in self.jobs:
            if job.state == "queued" and "remote_model" in job.needs and not online:
                job.state, job.waiting_for, job.reason = "waiting", ["remote_model"], "remote model unavailable"
                parked.append(job.id)
            elif job.state in ("waiting", "blocked") and all(self._available(r, job) for r in job.waiting_for):
                job.state, job.waiting_for, job.reason = "queued", [], ""
                resumed.append(job.id)
        if parked or resumed:
            self._save()
        if parked:
            self.emit("tasks_parked", tasks=parked, waiting_for="remote_model")
        if resumed:
            self.emit("tasks_reconciled", tasks=resumed)

    def _missing(self, job: Job) -> list[str]:
        have = {n.name for n in self.needs.all() if n.status == "satisfied"}
        return [r for r in job.requires if slug(r) not in have]

    def _runnable(self) -> list[Job]:
        now = _now()
        return [j for j in self.jobs if j.state == "queued" and not ((nb := _parse(j.not_before)) and nb > now)]

    def _next(self) -> Job | None:
        far = datetime.max.replace(tzinfo=timezone.utc)
        ready = self._runnable()
        return min(ready, key=lambda j: (_parse(j.deadline) or far, j.created)) if ready else None

    # --- dispatch --------------------------------------------------------------------------------

    def _dispatch(self, job: Job) -> None:
        if job.route == "unknown":
            self._set(job, "failed", reason=f"no capability named {job.capability!r}", kind="unknown")
            return
        if missing := self._missing(job):
            for r in missing:
                self.needs.add(r, f"job {job.id} requires it")
            self._set(job, "blocked", reason=f"missing prerequisite: {', '.join(missing)}",
                      waiting_for=[f"need:{slug(r)}" for r in missing], kind="prerequisite")
            return
        verdict = safety.check(job, home=self.home, vitals=self.vitals,
                               approved=safety.approvals(self.home), budget_usd=self.budget_usd)
        if not verdict.allow:
            self._set(job, verdict.state, reason=verdict.reason, waiting_for=verdict.waiting_for, kind="safety")
            return
        job.attempts += 1
        self._set(job, "running", attempt=job.attempts)  # saved before the risky part
        out = self._execute(job)
        if out.status == "done":
            self._finish(job, out)
        elif out.status == "waiting":
            job.attempts -= 1  # the network was down: not this job's failure
            self._set(job, "waiting", reason=out.error, waiting_for=["remote_model"], kind=out.kind)
        elif out.status == "retry" and job.attempts < MAX_ATTEMPTS:
            delay = BACKOFF_S * 2 ** (job.attempts - 1)
            job.not_before = (_now() + timedelta(seconds=delay)).isoformat(timespec="seconds")
            self._set(job, "queued", reason=out.error[:300], kind=out.kind, retry_in_s=delay)
        else:
            self._set(job, "failed", reason=out.error[:300],
                      kind=out.kind if out.status == "failed" else "retries_exhausted")

    def _execute(self, job: Job) -> Outcome:
        if job.route.startswith("capability:"):
            try:
                result = REGISTRY[job.capability].fn(**job.args)
            except (CapabilityError, TypeError) as exc:
                return Outcome("failed", kind="bad_input", error=str(exc))
            text = (f"Computed by `{job.capability}` (deterministic, no model).\n\n```json\n"
                    f"{json.dumps(result, indent=2, default=str)}\n```\n")
            return Outcome("done", text, {"result": result})
        if job.route == "recall":
            q = recall.recall_query(job.prompt) or job.prompt
            hits = recall.search(self.home, q)
            return Outcome("done", recall.render(q, hits), {"query": q, "hits": [asdict(h) for h in hits]})
        if job.route.startswith("pure:"):
            for route in PURE_ROUTES:
                if route.__name__ == job.route[5:] and (o := route(job.prompt)) is not None:
                    return Outcome("done", o.deliverable, o.detail)
            return Outcome("failed", kind="bad_input", error="the pure route no longer matches the prompt")
        return self._execute_model(job)

    def _execute_model(self, job: Job) -> Outcome:
        if not self._available("remote_model"):
            return Outcome("waiting", kind="remote_model_unavailable", error="remote model unavailable")
        workdir = self.home.episodes / job.id
        tree = self.mind.tree()
        res = self.executor.run(job.prompt, self.mind.system_prompt(tree), tree, workdir, self.timeout)
        if res.ok:
            self.state["breaker"] = {"failures": 0, "opened_at": ""}
            deliverable = (workdir / "deliverable.md").read_text(encoding="utf-8")
            return Outcome("done", deliverable, {"handled_by": res.handled_by, "cost_usd": res.cost_usd,
                                                 "llm_calls": res.llm_calls})
        # Was it the request, or the network? Ask the senses now rather than guess.
        reading, evs = self.senses.read(self.vitals, breaker_open=self._breaker_open(), force_probe=True)
        for ev in evs:
            self.events.emit(ev)
        self.vitals = reading
        if not reading["connectivity"]["network"] or not reading["connectivity"]["provider"]:
            self.emit("remote_call_failed", severity="warning", task=job.id, classified_as="unavailable")
            return Outcome("waiting", kind="remote_model_unavailable", error=res.error[:300])
        b = self.state["breaker"]
        b["failures"] += 1
        if b["failures"] >= BREAKER_FAILURES and not b["opened_at"]:
            b["opened_at"] = now_iso()
            self.emit("breaker_opened", severity="warning", failures=b["failures"],
                      cooldown_s=BREAKER_COOLDOWN_S)
        self.emit("remote_call_failed", severity="warning", task=job.id, classified_as="request_failed",
                  error=res.error[:300])
        return Outcome("retry", kind="request_failed", error=res.error)

    def _breaker_open(self) -> bool:
        b = self.state["breaker"]
        opened = _parse(b.get("opened_at", ""))
        if not opened:
            return False
        if (_now() - opened).total_seconds() >= BREAKER_COOLDOWN_S:
            # Half-open: allow one more try; one more failure opens it again.
            self.state["breaker"] = {"failures": BREAKER_FAILURES - 1, "opened_at": ""}
            self.emit("breaker_half_open")
            return False
        return True

    def _finish(self, job: Job, out: Outcome) -> None:
        workdir = self.home.episodes / job.id
        workdir.mkdir(parents=True, exist_ok=True)
        prompt = job.prompt or f"{job.capability}({json.dumps(job.args, default=str)})"
        (workdir / "prompt.md").write_text(prompt, encoding="utf-8")
        (workdir / "deliverable.md").write_text(out.deliverable, encoding="utf-8")
        inner = self._read(workdir / "route.json", None)  # the executor's own routing record, if any
        write_json(workdir / "route.json", {"route": job.route, "needs": job.needs, **out.detail,
                                            **({"executor": inner} if inner else {})})
        self.journal.record(Episode(id=job.id, prompt=prompt, domain=job.domain, replayable=job.replayable,
                                    mind_version=self.mind.version, ok=True))
        self._set(job, "done", deliverable=str(workdir.relative_to(self.home.root) / "deliverable.md"))
        if job.every_s:
            nxt = Job.from_dict({**asdict(job), "id": new_id(), "state": "queued", "attempts": 0,
                                 "interrupted": False, "overdue_reported": False, "reason": "",
                                 "created": now_iso(), "updated": now_iso(),
                                 "not_before": (_now() + timedelta(seconds=job.every_s)).isoformat(timespec="seconds")})
            self.jobs.append(nxt)
            self._save()
            self.emit("task_scheduled", task=nxt.id, after=job.id, not_before=nxt.not_before)

    # --- vitals ----------------------------------------------------------------------------------

    def task_sense(self) -> dict:
        counts: dict[str, int] = {}
        for j in self.jobs:
            counts[j.state] = counts.get(j.state, 0) + 1
        open_ = [j for j in self.jobs if j.state not in TERMINAL]
        return {
            "counts": counts,
            "deterministic_open": sum(1 for j in open_ if not j.needs and j.route != "unknown"),
            "needs_remote_model_open": sum(1 for j in open_ if "remote_model" in j.needs),
            "waiting": [{"task": j.id, "for": j.waiting_for} for j in self.jobs if j.state == "waiting"],
            "blocked": [{"task": j.id, "reason": j.reason} for j in self.jobs if j.state == "blocked"],
            "overdue": [j.id for j in open_ if j.overdue_reported],
        }

    def _write_vitals(self, reading: dict) -> None:
        self.vitals = {**reading, "tasks": self.task_sense(),
                       "memory": {"documents": len(recall.corpus(self.home)),
                                  "episodes": len(read_jsonl(self.home.journal))},
                       "breaker": dict(self.state["breaker"]), "halted": self.state["halted"],
                       "heartbeat": now_iso(), "pid": os.getpid()}
        write_json(self.vitals_file, self.vitals)
        self._save()


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
