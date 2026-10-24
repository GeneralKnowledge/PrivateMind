"""`privatebrain` command line."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .brain import Brain
from . import experiment as xp
from . import llm
from .capabilities import REGISTRY, ComputeFirstExecutor
from .executor import ClaudeCodeExecutor, SandboxedTextExecutor
from .home import DEFAULT_HOME, Home, safe_id
from .improve import BrainAdapter, DirectClaudeProposer, default_channel
from .journal import Journal
from .mind import Mind
from .needs import STATUSES, Needs
from . import lessons, recall, safety
from . import substrate as substrate_mod
from .events import EventLog
from .substrate import AlreadyRunning, Substrate

UNCONFINED_HELP = ("attended use only: allow the tool-using Claude Code executor and harness²'s proposer, "
                   "which run with host access and are NOT sandboxed")


def _gate_setup(home: Home, model: str, repeats: int = 3) -> xp.Setup:
    ledger = home.root / "llm_calls.jsonl"
    return xp.Setup(SandboxedTextExecutor(model=model, ledger=ledger), "sandboxed-text", model, repeats)


def _brain(home: Home, args) -> Brain:
    """The v0 executive. By default it does work with no tools (one sandboxed model call, after
    the compute-first routes) and does not improve itself. Only --allow-unconfined, typed by a
    person for that one command, gives it the tool-using executor and the harness² improver."""
    ledger = home.root / "llm_calls.jsonl"
    model = os.environ.get("PRIVATEBRAIN_MODEL") or llm.EVAL_MODEL
    if args.allow_unconfined:
        print(f"WARNING: {ClaudeCodeExecutor.__doc__.split(chr(10))[0]} {UNCONFINED_HELP}.", file=sys.stderr)
        executor = ClaudeCodeExecutor(unconfined_ok=True)
        if home.load_state().get("executor") == "compute-first":
            executor = ComputeFirstExecutor(executor, ledger=ledger)
        factory = lambda adapter: DirectClaudeProposer(  # noqa: E731
            adapter.spec.channels["proposer"], audit_dir=home.runs / "audit", unconfined_ok=True)
        gate = _gate_setup(home, llm.EVAL_MODEL)
    else:
        executor = ComputeFirstExecutor(SandboxedTextExecutor(model=model, ledger=ledger), model=model, ledger=ledger)
        factory, gate = None, None
    return Brain(home, executor, proposer_factory=factory, gate_setup=gate, timeout=args.timeout,
                 improve_k=args.k)


def _age(ts: str) -> str:
    if not ts:
        return "never"
    secs = (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds()
    return f"{secs:.0f}s ago" if secs < 120 else f"{secs / 60:.0f} min ago" if secs < 7200 else f"{secs / 3600:.1f} h ago"


def status_report(home: Home) -> dict:
    """Everything an operator needs to know, from the files the loop keeps, without a model."""
    code, hl = substrate_mod.health(home)
    sub = Substrate(home)
    vit = sub.vitals
    conn = vit.get("connectivity") or {}
    counts = {s: sum(j.state == s for j in sub.jobs) for s in ("queued", "running", "waiting", "blocked", "done", "failed")}
    approved = safety.approvals(home)
    needs_approval = [{"job": j.id, "for": safety.required_approval(j), "why": j.reason,
                       "command": f"privatebrain approve {j.id}"}
                      for j in sub.jobs if j.state == "blocked" and not safety.is_approved(j, approved)
                      and safety.required_approval(j)]
    ledger = home.root / "llm_calls.jsonl"
    spent = safety.spent_today(home)
    budget = safety.DAILY_MODEL_BUDGET_USD
    exps = [r for r in xp.log(home) if r.get("kind") != "adoption"]
    last = exps[-1] if exps else None
    state = home.load_state()
    return {
        "health": {"code": code, **hl},
        "remote_model": {"available": conn.get("remote_model"), "mode": conn.get("mode", "unknown"),
                         "reasons": conn.get("reasons", []), "as_of": conn.get("probed_at")},
        "jobs": counts,
        "waiting": [{"job": j.id, "for": j.waiting_for, "why": j.reason} for j in sub.jobs if j.state == "waiting"],
        "blocked": [{"job": j.id, "for": j.waiting_for, "why": j.reason} for j in sub.jobs if j.state == "blocked"],
        "failed": [{"job": j.id, "why": j.reason} for j in sub.jobs if j.state == "failed"][-5:],
        "needs_approval": needs_approval,
        "budget": {"spent_today_usd": spent, "daily_limit_usd": budget, "exceeded": spent >= budget,
                   "calls_with_unknown_cost": len(llm.unfinished_calls(ledger))},
        "mind": {"version": state["mind_version"], "versions": Mind(home).versions(), "auto_adopt": state["auto_adopt"],
                 "pending_approval": xp.pending(home),
                 "last_experiment": ({k: last.get(k) for k in ("id", "kind", "decision", "reasons", "finished")}
                                     if last else None)},
        "needs": [f"{n.name} ({n.status})" for n in Needs(home).all()],
        "inbox": len(Journal(home).queued()),
    }


def render_status(r: dict) -> str:
    h, rm, b, m = r["health"], r["remote_model"], r["budget"], r["mind"]
    beat = f"heartbeat {_age(h['heartbeat'] or '')}" if h.get("heartbeat") else "no heartbeat yet"
    lines = [f"brain:   {h['status']}" + (f" (pid {h['pid']})" if h.get("pid") else "") + f"; {beat}"]
    avail = "available" if rm["available"] else f"unavailable ({', '.join(rm['reasons']) or 'not probed yet'})"
    lines.append(f"mode:    {rm['mode']}; remote model {avail}; last probed {_age(rm['as_of'] or '')}")
    lines.append(f"budget:  ${b['spent_today_usd']:.4f} of ${b['daily_limit_usd']:.2f} today"
                 + (" EXCEEDED: model work waits" if b["exceeded"] else "")
                 + (f"; {b['calls_with_unknown_cost']} killed call(s) charged at their cap" if b["calls_with_unknown_cost"] else ""))
    lines.append("jobs:    " + ", ".join(f"{k} {v}" for k, v in r["jobs"].items()) + f"; {r['inbox']} not yet taken in")
    for key in ("waiting", "blocked"):
        for j in r[key]:
            lines.append(f"  {key} {j['job']} for {', '.join(j['for'])}: {j['why']}")
    for j in r["failed"]:
        lines.append(f"  failed {j['job']}: {j['why']}")
    if r["needs_approval"]:
        lines.append("approve: " + "; ".join(f"{a['job']} ({a['for']}): `{a['command']}`" for a in r["needs_approval"]))
    le = m["last_experiment"]
    lines.append(f"mind:    v{m['version']} (versions {m['versions']}, auto-adopt {'on' if m['auto_adopt'] else 'off'})"
                 + (f"; last experiment {le['id']} {le['decision']}: {'; '.join(le['reasons'] or [])[:160]}" if le else "")
                 + (f"; waiting for `mind approve`: {', '.join(m['pending_approval'])}" if m["pending_approval"] else ""))
    if r["needs"]:
        lines.append(f"needs:   {', '.join(r['needs'])}")
    return "\n".join(lines)


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
    k.add_argument("--allow-unconfined", action="store_true", help=UNCONFINED_HELP)
    st_ = sub.add_parser("status", help="is it running, online, within budget; jobs, approvals, mind")
    st_.add_argument("--json", action="store_true")
    sub.add_parser("health", help="for a supervisor: exit 0 healthy, 1 stalled, 2 not running")
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
    mr = msub.add_parser("rollback", help="make an earlier version live (default: the one before)")
    mr.add_argument("version", type=int, nargs="?")
    ma = msub.add_parser("approve", help="adopt a candidate that passed the gate while auto-adopt was off")
    ma.add_argument("experiment_id")
    mo = msub.add_parser("auto-adopt", help="adopt improvements without asking (on|off)")
    mo.add_argument("value", choices=("on", "off"))
    f = sub.add_parser("floor", help="the operator's boundaries")
    fsub = f.add_subparsers(dest="floor_cmd", required=True)
    fsub.add_parser("show")
    fsub.add_parser("accept", help="pin FLOOR.md after you have edited it on purpose")

    x = sub.add_parser("experiment", help="graded experiments on the mind and the executor")
    xsub = x.add_subparsers(dest="exp_cmd", required=True)
    xr = xsub.add_parser("run", help="one experiment: baseline, propose, evaluate, keep or reject")
    xr.add_argument("--optimizer", choices=("gepa", "harness2"), default="gepa")
    xr.add_argument("--domain", default="general", help="harness2: the journal domain to improve from")
    xr.add_argument("--allow-unconfined", action="store_true", help=UNCONFINED_HELP)
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
    xsub.add_parser("lessons", help="what earlier experiments found, with evidence and limits")
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
    ap = sub.add_parser("approve", help="approve what a blocked job is waiting for (once, for that reason only)")
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
        r = status_report(home)
        print(json.dumps(r, indent=2) if args.json else render_status(r))
    elif args.cmd == "health":
        code, report = substrate_mod.health(home)
        print(json.dumps(report))
        return code
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
            print(f"mind v{mind.rollback(args.version)} is live")
        elif args.mind_cmd == "approve":
            try:
                v = xp.adopt_candidate(home, args.experiment_id, approved_by="operator")
            except (xp.AdoptionRefused, ValueError) as exc:
                print(f"not adopted: {exc}", file=sys.stderr)
                return 1
            print(f"adopted as v{v}")
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
            if args.optimizer == "harness2":
                if not args.allow_unconfined:
                    print("harness² runs its editor with an unrestricted shell; it is not sandboxed. "
                          "Run it attended with --allow-unconfined.", file=sys.stderr)
                    return 2
                gate = setup(args.compute_first)
                opt = xp.Harness2Optimizer(
                    lambda: BrainAdapter(home, gate.executor, default_channel(), timeout=args.timeout),
                    DirectClaudeProposer(default_channel(), audit_dir=home.runs / "audit", unconfined_ok=True),
                    args.domain, k=args.k)
            else:
                opt = xp.GepaOptimizer(max_metric_calls=args.budget, ledger=ledger)
            st = xp.run_experiment(home, setup(args.compute_first), opt, resume=not args.no_resume)
            print((home.root / "experiments" / st["id"] / "RECORD.md").read_text(encoding="utf-8"))
        elif args.exp_cmd == "compare-executors":
            st = xp.compare_setups(home, setup(False), setup(True))
            state = home.load_state()
            if st["decision"] == "kept" and state.get("auto_adopt", True):
                state["executor"] = "compute-first"
                home.save_state(state)
            elif st["decision"] == "kept":
                print("kept by the gate; auto-adopt is off, so the executor is unchanged", file=sys.stderr)
            print((home.root / "experiments" / st["id"] / "RECORD.md").read_text(encoding="utf-8"))
        elif args.exp_cmd == "log":
            for row in xp.log(home):
                print(f"{row['id']}  {row['kind']:<16} {row['decision']:<16} ${row['total_cost_usd']}  "
                      f"{'; '.join(row['reasons'])[:120]}")
        elif args.exp_cmd == "lessons":
            for r in lessons.all_rows(home):
                ev = r.get("evidence", [{}])[0]
                print(f"{r.get('id')}  [{r.get('status')}]  {r.get('claim')}\n    evidence: experiment "
                      f"{ev.get('experiment')}, train gain {ev.get('train_gain')}, held-out delta "
                      f"{ev.get('heldout_delta')}, safety {'passed' if ev.get('safety') else 'FAILED'}; "
                      f"informed by {r.get('informed_by') or 'nothing earlier'}")
        else:
            print((home.root / "experiments" / safe_id(args.id) / "RECORD.md").read_text(encoding="utf-8"))
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
        found = [j for j in Substrate(home).jobs if j.id == args.job_id]
        if not found:
            print(f"no job {args.job_id!r}", file=sys.stderr)
            return 1
        try:
            print(f"{safety.approve(home, found[0], args.note)}: {args.job_id} "
                  f"({safety.required_approval(found[0])}); the loop picks it up on its next tick")
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 1
    elif args.cmd == "floor":
        if args.floor_cmd == "show":
            print(home.floor.read_text(encoding="utf-8"))
        else:
            mind.accept_floor()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
