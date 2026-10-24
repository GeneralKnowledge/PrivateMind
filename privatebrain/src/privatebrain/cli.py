"""`privatebrain` command line."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .brain import Brain
from . import experiment as xp
from . import llm
from .capabilities import REGISTRY, ComputeFirstExecutor
from .executor import ClaudeCodeExecutor, SandboxedTextExecutor
from .home import DEFAULT_HOME, Home
from .improve import DirectClaudeProposer, approve_pending
from .journal import Journal
from .mind import Mind
from .needs import STATUSES, Needs
from . import recall, safety
from .events import EventLog
from .substrate import AlreadyRunning, Substrate


def _brain(home: Home, args) -> Brain:
    executor = ClaudeCodeExecutor()
    if home.load_state().get("executor") == "compute-first":
        executor = ComputeFirstExecutor(executor, ledger=home.root / "llm_calls.jsonl")
    return Brain(
        home,
        executor,
        proposer_factory=lambda adapter: DirectClaudeProposer(
            adapter.spec.channels["proposer"], audit_dir=home.runs / "audit"
        ),
        timeout=args.timeout,
        improve_k=args.k,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="privatebrain", description=__doc__)
    p.add_argument("--home", type=Path, default=DEFAULT_HOME)
    p.add_argument("--timeout", type=int, default=1800, help="seconds per agent run")
    p.add_argument("--k", type=int, default=1, help="harness² recursion budget when improving")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create a brain home with the default floor and seed mind")
    t = sub.add_parser("task", help="queue a task")
    t.add_argument("prompt", nargs="?", default="")
    t.add_argument("--capability", default="", help="call this registry capability instead of a prompt")
    t.add_argument("--args", default="{}", help="JSON arguments for --capability")
    t.add_argument("--requires", action="append", default=[], help="a need that must be satisfied first")
    t.add_argument("--deadline", default="", help="ISO datetime")
    t.add_argument("--not-before", default="", help="ISO datetime")
    t.add_argument("--every", type=int, default=0, help="seconds: re-run this often once done")
    t.add_argument("--domain", default="general")
    t.add_argument(
        "--side-effects",
        action="store_true",
        help="the task acts on the world; it will never be replayed to improve the mind",
    )
    k = sub.add_parser("tick", help="let the executive choose and run activities")
    k.add_argument("--steps", type=int, default=1)
    sub.add_parser("status")
    n = sub.add_parser("need", help="manage needs")
    nsub = n.add_subparsers(dest="need_cmd", required=True)
    na = nsub.add_parser("add")
    na.add_argument("name")
    na.add_argument("why")
    ns = nsub.add_parser("set")
    ns.add_argument("name")
    ns.add_argument("status", choices=STATUSES)
    m = sub.add_parser("mind", help="inspect or roll back the mind")
    msub = m.add_subparsers(dest="mind_cmd", required=True)
    msub.add_parser("log")
    mr = msub.add_parser("rollback")
    mr.add_argument("version", type=int)
    ma = msub.add_parser("approve", help="adopt a pending mind proposal")
    ma.add_argument("episode_id")
    mo = msub.add_parser("auto-adopt", help="adopt improvements without asking (on|off)")
    mo.add_argument("value", choices=("on", "off"))
    f = sub.add_parser("floor", help="the operator's boundaries")
    fsub = f.add_subparsers(dest="floor_cmd", required=True)
    fsub.add_parser("show")
    fsub.add_parser("accept", help="pin FLOOR.md after you have edited it on purpose")

    x = sub.add_parser("experiment", help="graded experiments on the mind and the executor")
    xsub = x.add_subparsers(dest="exp_cmd", required=True)
    xr = xsub.add_parser("run", help="one experiment: baseline, propose, evaluate, keep or reject")
    xr.add_argument("--optimizer", choices=("gepa",), default="gepa")
    xr.add_argument("--budget", type=int, default=60, help="task runs GEPA may spend")
    xr.add_argument("--repeats", type=int, default=3)
    xr.add_argument("--model", default=llm.EVAL_MODEL, help="model the mind runs on")
    xr.add_argument("--compute-first", action="store_true", help="evaluate with deterministic routes on")
    xr.add_argument("--no-resume", action="store_true", help="start fresh even if one is unfinished")
    xc = xsub.add_parser("compare-executors", help="plain model executor vs compute-first routing")
    xc.add_argument("--repeats", type=int, default=3)
    xc.add_argument("--model", default=llm.EVAL_MODEL)
    xsub.add_parser("log")
    xs = xsub.add_parser("show")
    xs.add_argument("id")
    sub.add_parser("capabilities", help="list deterministic capabilities")

    r = sub.add_parser("run", help="the substrate loop: senses, safety, known work; models optional")
    r.add_argument("--interval", type=float, default=2.0, help="seconds to sleep when idle")
    r.add_argument("--ticks", type=int, default=None, help="stop after this many ticks")
    r.add_argument("--until-idle", action="store_true", help="stop when nothing is runnable")
    r.add_argument("--offline", action="store_true", help="treat the remote model as disconnected")
    r.add_argument("--probe-every", type=float, default=30.0, help="seconds between connectivity probes")
    r.add_argument("--model", default=llm.EVAL_MODEL, help="model for work that needs one")
    sub.add_parser("senses", help="one reading of every sense, without running the loop")
    sub.add_parser("jobs", help="the substrate's jobs and their states")
    e = sub.add_parser("events", help="the structured event journal")
    e.add_argument("--tail", type=int, default=30)
    e.add_argument("--type", default=None)
    rc = sub.add_parser("recall", help="search local memory (BM25, no model)")
    rc.add_argument("query")
    ap = sub.add_parser("approve", help="approve a blocked job (the safety layer reads this)")
    ap.add_argument("job_id")
    ap.add_argument("--note", default="")

    args = p.parse_args(argv)
    home = Home(args.home.expanduser())
    mind = Mind(home)

    if args.cmd == "init":
        if home.exists():
            print(f"{home.root} already holds a brain", file=sys.stderr)
            return 1
        mind.seed()
        print(f"Brain created at {home.root}. Edit {home.floor}, then `privatebrain floor accept`.")
        return 0
    if not home.exists():
        print(f"no brain at {home.root}; run `privatebrain init`", file=sys.stderr)
        return 1

    if args.cmd == "task":
        if not args.prompt and not args.capability:
            print("give a prompt or --capability", file=sys.stderr)
            return 2
        task = Journal(home).enqueue(
            args.prompt, domain=args.domain, replayable=not args.side_effects,
            capability=args.capability, args=json.loads(args.args), requires=args.requires,
            deadline=args.deadline, not_before=args.not_before, every_s=args.every,
        )
        print(f"queued {task.id}")
    elif args.cmd == "tick":
        brain = _brain(home, args)
        for _ in range(args.steps):
            r = brain.tick()
            print(f"[{r.activity}] {r.detail}")
    elif args.cmd == "status":
        state = home.load_state()
        j = Journal(home)
        print(
            json.dumps(
                {
                    "home": str(home.root),
                    "mind_version": mind.version,
                    "versions": mind.versions(),
                    "auto_adopt": state["auto_adopt"],
                    "pending_adoptions": state["pending_adoptions"],
                    "queued_tasks": len(j.queued()),
                    "episodes": len(j.episodes()),
                    "needs": [f"{n.name} ({n.status})" for n in Needs(home).all()],
                    "recent_activity": state["activities"][-10:],
                },
                indent=2,
            )
        )
    elif args.cmd == "need":
        needs = Needs(home)
        if args.need_cmd == "add":
            print(needs.add(args.name, args.why).name)
        else:
            needs.set_status(args.name, args.status)
    elif args.cmd == "mind":
        if args.mind_cmd == "log":
            for v in mind.versions():
                marker = "*" if v == mind.version else " "
                head = (home.mind_versions / str(v) / "ADOPTION.md").read_text().splitlines()
                print(f"{marker} v{v}  {next((h for h in head if 'source' in h), '')}")
        elif args.mind_cmd == "rollback":
            mind.rollback(args.version)
        elif args.mind_cmd == "approve":
            print(f"adopted as v{approve_pending(home, args.episode_id)}")
        else:
            state = home.load_state()
            state["auto_adopt"] = args.value == "on"
            home.save_state(state)
    elif args.cmd == "experiment":
        ledger = home.root / "llm_calls.jsonl"

        def setup(compute_first: bool) -> xp.Setup:
            plain = SandboxedTextExecutor(model=args.model, ledger=ledger)
            if compute_first:
                return xp.Setup(ComputeFirstExecutor(plain, model=args.model, ledger=ledger),
                                "compute-first/2+sandboxed-text", args.model, args.repeats)
            return xp.Setup(plain, "sandboxed-text", args.model, args.repeats)

        if args.exp_cmd == "run":
            opt = xp.GepaOptimizer(max_metric_calls=args.budget, ledger=ledger)
            st = xp.run_experiment(home, setup(args.compute_first), opt, resume=not args.no_resume)
            print((home.root / "experiments" / st["id"] / "RECORD.md").read_text(encoding="utf-8"))
        elif args.exp_cmd == "compare-executors":
            st = xp.compare_setups(home, setup(False), setup(True))
            if st["decision"] == "kept":
                state = home.load_state()
                state["executor"] = "compute-first"
                home.save_state(state)
            print((home.root / "experiments" / st["id"] / "RECORD.md").read_text(encoding="utf-8"))
        elif args.exp_cmd == "log":
            for row in xp.log(home):
                print(f"{row['id']}  {row['kind']:<16} {row['decision']:<16} ${row['total_cost_usd']}  "
                      f"{'; '.join(row['reasons'])[:120]}")
        else:
            print((home.root / "experiments" / args.id / "RECORD.md").read_text(encoding="utf-8"))
    elif args.cmd == "capabilities":
        print(json.dumps([c.describe() for c in REGISTRY.values()], indent=2))
    elif args.cmd == "run":
        sub_ = Substrate(home, forced_offline=args.offline, probe_every_s=args.probe_every,
                         model=args.model, timeout=args.timeout)
        try:
            sub_.run(max_ticks=args.ticks, interval=args.interval, until_idle=args.until_idle)
        except AlreadyRunning as exc:
            print(exc, file=sys.stderr)
            return 1
        print(json.dumps(sub_.vitals.get("tasks", {}).get("counts", {})))
    elif args.cmd == "senses":
        sub_ = Substrate(home)
        reading, _ = sub_.senses.read({}, breaker_open=False, force_probe=True)
        print(json.dumps({**reading, "tasks": sub_.task_sense()}, indent=2))
    elif args.cmd == "jobs":
        for j in Substrate(home).jobs:
            why = f"  ({j.reason})" if j.reason else ""
            print(f"{j.id}  {j.state:<8} {j.route:<36} {(j.prompt or j.capability)[:50]!r}{why}")
    elif args.cmd == "events":
        for ev in EventLog(home).tail(args.tail, type=args.type):
            print(json.dumps(ev))
    elif args.cmd == "recall":
        print(recall.render(args.query, recall.search(home, args.query)), end="")
    elif args.cmd == "approve":
        safety.approve(home, args.job_id, args.note)
        print(f"approved {args.job_id}")
    elif args.cmd == "floor":
        if args.floor_cmd == "show":
            print(home.floor.read_text(encoding="utf-8"))
        else:
            mind.accept_floor()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
