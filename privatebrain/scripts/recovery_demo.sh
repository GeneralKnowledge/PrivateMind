#!/usr/bin/env bash
# Process recovery, for real: an external supervisor (scripts/supervise.sh) restarts the loop
# after SIGKILL and after a stall (SIGSTOP), and work is neither lost, repeated, nor blindly
# replayed. Needs a logged-in `claude` CLI for the model tasks (a few Haiku calls, about $0.01).
#
#   scripts/recovery_demo.sh <empty-dir>
set -euo pipefail
H="${1:?usage: recovery_demo.sh <empty-dir>}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PB=(python -m privatebrain.cli --home "$H")
say() { printf '\n### %s\n' "$*"; }
loop_pid() { "${PB[@]}" health | python -c 'import json,sys; print(json.load(sys.stdin).get("pid") or "")'; }
wait_for() { for _ in $(seq "${2:-300}"); do grep -q "$1" "$H/events.jsonl" 2>/dev/null && return 0; sleep 0.2; done; echo "timed out waiting for $1"; return 1; }
count() { grep -c "\"type\": \"$1\"" "$H/events.jsonl" || true; }

say "init, and a supervisor that checks every 2 s"
"${PB[@]}" init >/dev/null
"$HERE/supervise.sh" "$H" 2 --interval 1 --probe-every 5 &
SUP=$!
trap 'kill $SUP 2>/dev/null; P=$(loop_pid); [ -n "$P" ] && kill -CONT "$P" 2>/dev/null; [ -n "$P" ] && kill "$P" 2>/dev/null; true' EXIT
wait_for '"type": "started"' 100

say "1. SIGKILL during a model call on a task that acts on the world"
"${PB[@]}" task "Draft a two-line email to the landlord confirming the boiler visit on Thursday." --side-effects
"${PB[@]}" task "" --capability money.sum_line_items --args '{"items":[{"label":"service","unit_price":"89.00"}],"currency":"GBP"}'
wait_for '"type": "task_running"'
P=$(loop_pid); kill -KILL "$P"; echo "killed loop pid $P mid-call"
wait_for '"type": "crash_recovered"' 100
sleep 3
"${PB[@]}" jobs
"${PB[@]}" status

say "2. the operator checks nothing was sent, approves the retry once; it runs once"
J=$("${PB[@]}" jobs | awk '$2=="blocked"{print $1}' | head -1)
"${PB[@]}" approve "$J" --note "checked: nothing went out"
"${PB[@]}" approve "$J" || true          # a second approval is refused: nothing to approve now, or already approved
for _ in $(seq 200); do "${PB[@]}" jobs | grep -q "^$J  done" && break; sleep 0.3; done
"${PB[@]}" jobs

say "3. a stall: SIGSTOP the loop; health turns stale and the supervisor replaces it"
P=$(loop_pid); kill -STOP "$P"; echo "stopped loop pid $P at $(date -u +%T)"
for _ in $(seq 120); do [ "$(count crash_recovered)" -ge 2 ] && break; sleep 1; done
echo "replaced at $(date -u +%T); new pid $(loop_pid)"
kill -KILL "$P" 2>/dev/null || true
grep 'supervise:' "$H/supervise.log"

say "4. after both restarts: every job ran to an end state exactly once"
"${PB[@]}" task "recall boiler"
sleep 4
"${PB[@]}" jobs
python - "$H" <<'PY'
import collections, json, sys
h = sys.argv[1]
ev = [json.loads(l) for l in open(f"{h}/events.jsonl")]
done = collections.Counter(e["task"] for e in ev if e["type"] == "task_done")
print("task_done per job:", dict(done), "-> max", max(done.values()))
print("events:", dict(collections.Counter(e["type"] for e in ev)))
calls = [json.loads(l) for l in open(f"{h}/llm_calls.jsonl")]
fin = [c for c in calls if c.get("status") != "started"]
ids = {c["call_id"] for c in fin}
lost = [c for c in calls if c.get("status") == "started" and c["call_id"] not in ids]
print(f"model ledger: {len(fin)} finished calls ${sum(c['cost_usd'] for c in fin):.4f}; "
      f"{len(lost)} killed call(s) with unknown cost, charged at cap ${sum(c['max_budget_usd'] for c in lost)}")
PY
"${PB[@]}" status
