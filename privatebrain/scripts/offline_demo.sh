#!/usr/bin/env bash
# Offline survival, for real: the loop runs inside a network namespace with no interfaces up
# (`unshare -rn`), so no model, provider or proxy is reachable. Needs Linux with unprivileged
# user namespaces, and a logged-in `claude` CLI for the online phases (about $0.01 of Haiku).
#
#   scripts/offline_demo.sh <empty-dir>
set -euo pipefail
H="${1:?usage: offline_demo.sh <empty-dir>}"
PB=(python -m privatebrain.cli --home "$H")
OFFLINE=(unshare -rn "${PB[@]}")
say() { printf '\n### %s\n' "$*"; }

say "init"
"${PB[@]}" init >/dev/null
mkdir -p "$H/notes"
cat >"$H/notes/house.md" <<'NOTE'
# House
The boiler engineer is Sam Okafor, booked for Thursday 29 October 2026 at 10:00.
The landlord prefers email over phone calls.
NOTE

say "phase 1 (online): a model task starts, then the process is killed with SIGKILL mid-call"
"${PB[@]}" task "In three short bullet points, what should a tenant check before a boiler service visit?" --domain home
"${PB[@]}" run --interval 0.2 --probe-every 0 >/dev/null 2>&1 &
PID=$!
for _ in $(seq 100); do grep -q '"task_running"' "$H/events.jsonl" 2>/dev/null && break; sleep 0.1; done
sleep 1
kill -9 "$PID"; wait "$PID" 2>/dev/null || true
"${PB[@]}" jobs

say "phase 2 (offline, no network interfaces): recovery, known work, memory, honest waiting"
CALLS_BEFORE=$( (cat "$H/llm_calls.jsonl" 2>/dev/null || true) | wc -l)
"${PB[@]}" task "" --capability money.sum_line_items \
  --args '{"items":[{"label":"boiler service","unit_price":"89.00"},{"label":"filter","quantity":2,"unit_price":"12.45"}],"currency":"GBP","budget":"120"}'
"${PB[@]}" task "Today is 2026-10-26. Do any of these clash?
- Thu 29 Oct 09:30-10:30 Dentist
- Thu 29 Oct 10:00-11:00 Boiler service
- Fri 30 Oct 14:00-15:00 Review"
"${PB[@]}" task "What do you know about the boiler engineer?"
"${PB[@]}" task "recall: my passport renewal"
"${PB[@]}" task "" --capability stocks.buy --args '{"ticker":"ACME"}'
"${PB[@]}" task "" --capability dates.normalize --args '{"text":"Sync calendar for Wed 4 November 2026"}' --requires calendar-access
"${PB[@]}" task "Email the landlord that the boiler visit is on Thursday" --side-effects
"${PB[@]}" task "Total these costs in GBP:
- two radiator valves at 14.20 each
- one bleed key at 3.50"
"${PB[@]}" task "Write a short note to self about the visit" --deadline 2026-10-01T00:00:00+00:00
"${OFFLINE[@]}" run --until-idle --interval 0 --probe-every 0
"${OFFLINE[@]}" senses | python -c 'import json,sys; d=json.load(sys.stdin); print(json.dumps({"connectivity": d["connectivity"], "tasks": d["tasks"]}, indent=1))'
"${PB[@]}" jobs
"${OFFLINE[@]}" status
CALLS_AFTER=$( (cat "$H/llm_calls.jsonl" 2>/dev/null || true) | wc -l)
echo "model ledger rows written during the offline phase: $((CALLS_AFTER - CALLS_BEFORE))"

say "phase 3 (online again): parked model work is reconciled and runs (the email task can only draft: no tools)"
"${PB[@]}" need set calendar-access satisfied   # the operator provides what was missing
"${PB[@]}" run --until-idle --interval 0 --probe-every 0
"${PB[@]}" jobs

say "phase 4 (offline again): what the model produced is retrievable without it"
"${PB[@]}" task "recall: boiler service visit tenant check"
"${OFFLINE[@]}" run --until-idle --interval 0 --probe-every 0
"${PB[@]}" jobs | tail -1
cat "$H/episodes/$("${PB[@]}" jobs | tail -1 | cut -d" " -f1)/deliverable.md"

say "events"
"${PB[@]}" events --tail 1000 | python -c '
import collections, json, sys
rows = [json.loads(l) for l in sys.stdin]
print(dict(collections.Counter(r["type"] for r in rows)))
for r in rows:
    if r["type"] in ("crash_recovered", "remote_model_unavailable", "remote_model_available", "mode_changed",
                     "tasks_parked", "tasks_reconciled", "task_overdue", "task_blocked", "task_failed"):
        print(json.dumps(r))'
python - "$H" <<'PY'
import collections, json, sys
h = sys.argv[1]
rows = [json.loads(l) for l in open(f"{h}/llm_calls.jsonl")]
fin = [r for r in rows if r.get("status") != "started"]
ids = {r["call_id"] for r in fin if r.get("call_id")}
killed = [r for r in rows if r.get("status") == "started" and r["call_id"] not in ids]
print(f"model ledger: {len(fin)} completed calls, ${sum(r['cost_usd'] for r in fin):.4f}; "
      f"{len(killed)} killed mid-call (cost unknown, charged at cap ${sum(r['max_budget_usd'] for r in killed)})")
ev = [json.loads(l) for l in open(f"{h}/events.jsonl")]
done = collections.Counter(e["task"] for e in ev if e["type"] == "task_done")
print("jobs finished more than once:", [t for t, n in done.items() if n > 1] or "none")
PY
"${PB[@]}" status
