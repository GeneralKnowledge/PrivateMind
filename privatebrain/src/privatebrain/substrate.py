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

Only this loop writes `jobs.json`, `substrate.json` and `vitals.json`. It holds an exclusive
`flock` on `substrate.lock` for as long as it runs: the kernel releases it when the process dies,
however it dies, so a second loop is kept out and a dead one never blocks a restart (a pid alone
can be reused). The pid written inside the lock file, left behind by a process that did not stop
cleanly, is how the next start knows to recover.

Delivery guarantees, given a durable disk: a queued task is never lost (it is copied into
`jobs.json` before it leaves `tasks.jsonl`); a job that finished is never run again (its journal
entry is checked on recovery); a replayable job interrupted by a crash is run again (at least
once); a job that acts on the world is never re-run after an interruption without a fresh,
scoped approval (at most once unless the operator says otherwise).
"""

from __future__ import annotations

import fcntl
import json
import os
import signal
import time
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import capabilities, llm, recall, safety
from .capabilities import (PURE_ROUTES, REGISTRY, CapabilityError, CapabilityFault, ComputeFirstExecutor,
                           budget_route_applies)
from .events import EventLog, event, now_iso
from .executor import Executor, SandboxedTextExecutor
from .home import Home, read_jsonl, safe_id, write_json
from .journal import Episode, Journal, new_id
from .mind import Mind
from .needs import Needs, slug
from .senses import Probes, Senses

MAX_ATTEMPTS = 3
BACKOFF_S = 30  # first retry delay; doubles each attempt
BREAKER_FAILURES = 3  # consecutive failed model calls before the breaker opens
BREAKER_COOLDOWN_S = 300
TERMINAL = ("done", "failed")
# Model failures that say nothing about the job: they open the breaker and the job waits for
# the model, without spending one of its attempts (see llm.classify).
NOT_THE_JOBS_FAULT = ("client_missing", "auth", "provider")
MODEL_CALL_CAP_USD = float(os.environ.get("PRIVATEBRAIN_CALL_CAP_USD", "0.10"))


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
            SandboxedTextExecutor(model=model, ledger=ledger, max_budget_usd=MODEL_CALL_CAP_USD),
            model=model, ledger=ledger, max_budget_usd=MODEL_CALL_CAP_USD)
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
        self._lock_fd: int | None = None
        self.interval = 2.0
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
        fd = os.open(self.lock_file, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            raise AlreadyRunning(f"a substrate loop is already running (pid {_lock_pid(self.lock_file)})")
        self._lock_fd = fd
        prev_pid = _lock_pid(self.lock_file)
        os.ftruncate(fd, 0)
        os.pwrite(fd, str(os.getpid()).encode(), 0)
        if prev_pid:
            self.emit("crash_recovered", severity="warning", previous_pid=prev_pid,
                      last_heartbeat=self.vitals.get("heartbeat", ""))
        finished = {e.id for e in self.journal.episodes()}
        for job in self.jobs:
            if job.state != "running":
                continue
            job.interrupted = True
            if job.id in finished:
                # It finished and was journaled; only the last state write was lost. Never re-run.
                self._set(job, "done", reason="finished before the crash (found in the journal)",
                          recovered=True)
            elif job.attempts >= MAX_ATTEMPTS:
                self._set(job, "failed", reason=f"interrupted {job.attempts} times", kind="crashed")
            elif not job.replayable:
                # It may already have acted on the world: tell the operator now, do not retry.
                # The approval this needs is scoped to this attempt, so no earlier one counts.
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
        self.vitals["stopped"] = now_iso()
        write_json(self.vitals_file, self.vitals)
        if self._lock_fd is not None:
            os.ftruncate(self._lock_fd, 0)  # an empty lock file means "stopped cleanly"
            fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            os.close(self._lock_fd)
            self._lock_fd = None
        self._started = False

    def run(self, *, max_ticks: int | None = None, interval: float = 2.0, until_idle: bool = False) -> None:
        def handle(signum, _frame):
            self._stop = True

        old = {s: signal.signal(s, handle) for s in (signal.SIGTERM, signal.SIGINT)}
        self.interval = interval
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
        rows, bad = self.journal.inbox()
        if not rows and not bad:
            return
        known = {j.id for j in self.jobs}
        taken, received, rejected = set(), [], []
        for row in rows:
            rid = row.get("id")
            taken.add(rid)
            if rid in known:
                continue  # copied before a crash, removed after: already a job
            try:
                safe_id(rid)
                job = Job.from_dict({**row, "created": now_iso(), "updated": now_iso()})
                if not isinstance(job.args, dict) or not isinstance(job.requires, list):
                    raise ValueError("args must be an object and requires a list")
                job.route, job.needs = plan(job)
            except Exception as exc:  # a malformed row is refused, never guessed at
                rejected.append({"row": json.dumps(row, default=str)[:300], "error": str(exc)[:300]})
                continue
            self.jobs.append(job)
            known.add(job.id)
            received.append(job)
        self._save()  # durable here first ...
        bad = self.journal.remove(taken)  # ... then gone from the inbox
        for job in received:
            self.emit("task_received", task=job.id, route=job.route, needs=job.needs, origin=job.origin)
        for r in rejected:
            self.emit("task_rejected", severity="warning", **r)
        if bad:
            self.emit("task_rejected", severity="warning", malformed_lines=len(bad),
                      kept_in="tasks.rejected.jsonl")

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
            return job is not None and safety.is_approved(job, safety.approvals(self.home))
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
                why = ", ".join(self.vitals.get("connectivity", {}).get("reasons", [])) or "not probed yet"
                job.state, job.waiting_for, job.reason = "waiting", ["remote_model"], f"remote model unavailable: {why}"
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
            kind = "bad_input" if verdict.state == "failed" else "safety"
            self._set(job, verdict.state, reason=verdict.reason, waiting_for=verdict.waiting_for, kind=kind)
            return
        job.attempts += 1
        self._set(job, "running", attempt=job.attempts)  # saved before the risky part
        # Tell a supervisor this tick may be long, so a slow model call is not mistaken for a hang.
        self.vitals["busy"] = {"task": job.id, "route": job.route, "since": now_iso(),
                               "limit_s": self.timeout if "remote_model" in job.needs else 60}
        self._write_vitals(self.vitals)
        out = self._execute(job)
        self.vitals.pop("busy", None)
        if out.status == "done":
            self._finish(job, out)
        elif out.status == "waiting":
            job.attempts -= 1  # the network, provider or client was at fault, not this job
            self._set(job, "waiting", reason=out.error[:300], waiting_for=["remote_model"], kind=out.kind)
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
                result = capabilities.call(job.capability, job.args)
            except CapabilityError as exc:
                return Outcome("failed", kind="bad_input", error=str(exc))
            except CapabilityFault as exc:
                return Outcome("failed", kind="capability_fault", error=str(exc))
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
        conn = reading["connectivity"]
        if not conn["network"] or not conn["provider"] or not conn["model_client"]:
            self.emit("remote_call_failed", severity="warning", task=job.id, classified_as="unavailable",
                      error_kind=res.error_kind, error=res.error[:300])
            return Outcome("waiting", kind="remote_model_unavailable", error=res.error[:300])
        b = self.state["breaker"]
        b["failures"] += 1
        if res.error_kind in NOT_THE_JOBS_FAULT:
            # The provider or the client is at fault (bad credentials, overload, missing CLI):
            # the same failure would hit every job, so stop calling at once and wait.
            b["failures"] = max(b["failures"], BREAKER_FAILURES)
        if b["failures"] >= BREAKER_FAILURES and not b["opened_at"]:
            b["opened_at"] = now_iso()
            self.emit("breaker_opened", severity="warning", failures=b["failures"],
                      cooldown_s=BREAKER_COOLDOWN_S, error_kind=res.error_kind)
        if res.error_kind in NOT_THE_JOBS_FAULT:
            self.emit("remote_call_failed", severity="warning", task=job.id, classified_as=res.error_kind,
                      error=res.error[:300])
            return Outcome("waiting", kind=f"model_{res.error_kind}", error=res.error[:300])
        self.emit("remote_call_failed", severity="warning", task=job.id, classified_as="request_failed",
                  error_kind=res.error_kind or "unknown", error=res.error[:300])
        return Outcome("retry", kind=res.error_kind or "request_failed", error=res.error)

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
                       "heartbeat": now_iso(), "pid": os.getpid(), "interval_s": self.interval}
        write_json(self.vitals_file, self.vitals)
        self._save()


def health(home: Home, *, now: datetime | None = None) -> tuple[int, dict]:
    """(exit code, report) for a supervisor. 0: running and its heartbeat is fresh, or it is
    inside a model call that is still within its time limit. 1: the process holds the lock but
    its heartbeat is stale: hung or stopped (SIGSTOP), so restart it. 2: not running.

    Idle is not stale: an idle loop still beats every `interval_s`. A slow model call is not
    stale either: before it starts, the loop records `busy` with the call's time limit."""
    now = now or _now()
    vitals = Substrate._read(home.root / "vitals.json", {})
    pid = loop_running(home)
    beat = _parse(vitals.get("heartbeat", ""))
    age = round((now - beat).total_seconds(), 1) if beat else None
    interval = float(vitals.get("interval_s") or 2.0)
    stale_after = max(30.0, 3 * interval + 10)
    busy = vitals.get("busy")
    report = {"running": bool(pid), "pid": pid if pid and pid > 0 else None, "heartbeat": vitals.get("heartbeat"),
              "heartbeat_age_s": age, "stale_after_s": stale_after, "busy": busy,
              "halted": vitals.get("halted") or ""}
    if not pid:
        report["status"] = "stopped cleanly" if vitals.get("stopped") else "not running"
        if not vitals.get("stopped") and _lock_pid(home.root / "substrate.lock"):
            report["status"] = "not running (died without stopping; the next start recovers)"
        return 2, report
    if busy and (since := _parse(busy.get("since", ""))):
        limit = float(busy.get("limit_s") or 300) + 30
        took = (now - since).total_seconds()
        report["status"] = f"busy on {busy.get('task')} for {took:.0f}s (limit {limit:.0f}s)"
        return (0, report) if took <= limit else (1, {**report, "status": report["status"] + ": stalled"})
    if age is None or age > stale_after:
        report["status"] = f"stalled: heartbeat {age}s old (stale after {stale_after:.0f}s)"
        return 1, report
    report["status"] = "halted: the floor changed" if report["halted"] else "healthy"
    return 0, report


def loop_running(home: Home) -> int | None:
    """The pid of the live substrate loop, or None. Asks the kernel (the flock), not the pid."""
    path = home.root / "substrate.lock"
    if not path.exists():
        return None
    fd = os.open(path, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except BlockingIOError:
        return _lock_pid(path) or -1
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)
        return None
    finally:
        os.close(fd)


def _lock_pid(path: Path) -> int | None:
    try:
        return int(path.read_text().strip() or 0) or None
    except (OSError, ValueError):
        return None


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
