"""`privatebrain` command line."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .brain import Brain
from .executor import ClaudeCodeExecutor
from .home import DEFAULT_HOME, Home
from .improve import DirectClaudeProposer, approve_pending
from .journal import Journal
from .mind import Mind
from .needs import STATUSES, Needs


def _brain(home: Home, args) -> Brain:
    return Brain(
        home,
        ClaudeCodeExecutor(),
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
    t.add_argument("prompt")
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
        task = Journal(home).enqueue(
            args.prompt, domain=args.domain, replayable=not args.side_effects
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
    elif args.cmd == "floor":
        if args.floor_cmd == "show":
            print(home.floor.read_text(encoding="utf-8"))
        else:
            mind.accept_floor()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
