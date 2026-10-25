# The substrate: PrivateBrain without a model

The question this answers: does PrivateBrain stay alive, coherent and useful when its most
intelligent component is unavailable? It is the first vertical slice of a layered design:

| Level | Role | Status |
|---|---|---|
| 4. Remote LLM | Hard reasoning, research, synthesis. Optional. | Plugs in through the existing executors |
| 3. Local CPU model | Interpreting, explaining, classifying, planning. Optional. | **Not built.** The slice had to work first |
| 2. Cognitive substrate | Routing, rules, capabilities, retrieval, scheduling | `substrate.py`, `capabilities.py`, `recall.py` |
| 1. Reflexes and vitals | Loop, clock, persistence, health, safety, recovery | `substrate.py`, `senses.py`, `safety.py`, `events.py` |

Lower levels never trust higher ones blindly. A model can only propose work through
`Substrate.propose`, which checks every field's type and the capability's arguments, and stamps
the job `origin: "model"`. Model work runs through `llm.call` with no tools. Approvals come from
the operator's `approvals.jsonl`, which the loop reads and never writes; each one names a job and
the one reason it was blocked, so it cannot be reused for a later retry.

## How it works

`privatebrain run` is a persistent loop. Each tick does six things in order:

1. **Floor check.** A tampered `FLOOR.md` halts all work. The loop keeps sensing and writing a heartbeat, so the halt is visible.
2. **Inbox.** Tasks queued with `privatebrain task` become jobs with a state, a route and the resources that route needs.
3. **Senses.** The loop reads every sense and raises events only when something changes. The senses are:
   - **temporal**: wall clock against the monotonic clock, overdue deadlines, recurring jobs.
   - **internal**: pid, uptime, RSS, load, free memory and disk, whether storage is writable, local model status.
   - **connectivity**: is the network up (a TCP connect to the proxy or provider), does the provider answer HTTP (any status counts, and no credentials are sent), is the model client installed, and is the call breaker closed.
   - **tasks and memory**: counts by state, open work split into deterministic and needs-model, what each waiting job is waiting for, why each blocked job is blocked, and how many documents are in local memory.
4. **Reconcile.** While the remote model is away, queued model work is parked. A waiting or blocked job returns to the queue once whatever it was waiting for is available again.
5. **One job.** It is routed by ordinary rules, never by asking a model:
   - a registry capability (`--capability`);
   - a memory lookup ("recall …", "what do you know about …"), answered by BM25 over episodes, lessons, long-term memory and `notes/`;
   - a pure compute route (calendar clashes);
   - otherwise, work that needs the remote model.

   Safety checks run first, every time a job is dispatched: a capability's arguments are
   checked again here, whatever was checked when the job was created, and a capability's output
   is re-derived independently (`capabilities.call`) before it counts as a result. The job is
   marked running and saved before it runs, and `vitals.json` records that the loop is `busy`
   with it and for how long it may take.
6. **Vitals.** The reading, the job counts and a heartbeat go to `vitals.json`, so an external supervisor can watch the heartbeat.

The loop behaves differently depending on why something cannot proceed:

| Situation | What happens |
|---|---|
| Remote model unreachable | Model jobs go to `waiting` for `remote_model`. Everything else carries on. |
| A model call fails and the network, provider or model client is down | The job goes to `waiting`. The attempt is not counted against it. |
| The provider rejects the credentials, is overloaded, or rate-limits (401/403/429/5xx), or the CLI is missing | Not the job's fault: the breaker opens at once (no point sending more), the job waits for the model, and the attempt is not counted. |
| The provider refuses this request (other 4xx, e.g. an unknown model), a timeout, or an unrecognised error | Counted against the job: retried with exponential backoff, at most 3 attempts. After 3 consecutive failures the breaker opens for 5 minutes, then half-opens. |
| A job requires a need that is not satisfied | The job is `blocked` and the need is recorded for the next batched ask. It runs once the operator satisfies the need. |
| A capability that does not exist | `failed`, kind `unknown`. This means *I do not know how*, which is different from `waiting`, *I cannot do this right now*. |
| Bad input to a capability (wrong type, unknown argument, a float for money) | `failed`, kind `bad_input`. Not retried. It used to crash the loop. |
| A capability raises something undocumented, or its output fails the independent recheck | `failed`, kind `capability_fault`. Never reported as a result. |
| A malformed line in `tasks.jsonl`, or a task id that is not a safe path part | Not run. Moved to `tasks.rejected.jsonl` with a `task_rejected` event. |
| A crash (SIGKILL) during a run | The next start raises `crash_recovered`. A job whose episode is already in the journal is marked done, not re-run. A replayable job is requeued, with at most 3 interruptions before it fails. A side-effecting job is `blocked` for an approval scoped to that attempt, because it may already have acted. |
| A side-effecting job proposed by a model | `blocked` until `privatebrain approve <id>`. That approval covers this run only; it does not cover a retry after a crash. |
| Today's model spend reaches `PRIVATEBRAIN_DAILY_BUDGET_USD` (default $1) | Model jobs wait for `model_budget`. A call killed mid-flight has no known cost and is charged at its cap (`PRIVATEBRAIN_CALL_CAP_USD`, default $0.10). |
| Storage not writable | Every job waits, because results could not be kept. |

Only one loop runs at a time: it holds an exclusive `flock` on `substrate.lock`, which the kernel
releases however the process dies, so a dead loop never blocks a restart (a pid alone can be
reused by another process). Every state change is an event in `events.jsonl`, which is
append-only. Here is an event from the run below:

```json
{"type": "remote_model_unavailable", "timestamp": "2026-10-24T13:58:39+00:00", "severity": "warning",
 "source": "connectivity", "affected_capability": "remote_reasoning", "reasons": ["network_unavailable"]}
```

## Recovery and supervision

The brain does not keep itself alive; an external supervisor does. `privatebrain health` is
what the supervisor asks:

| exit | meaning | supervisor action |
|---|---|---|
| 0 | running, heartbeat fresh; or inside a model call still within its time limit (`busy` in `vitals.json`) | none |
| 1 | holds the lock but the heartbeat is stale (hung, or SIGSTOPped) | SIGKILL it and start a new one |
| 2 | not running (stopped cleanly, or died: `status` says which) | start it |

An idle loop is not stale: it writes a heartbeat every `--interval` seconds whether or not there
is work. A heartbeat is stale after `max(30 s, 3 x interval + 10 s)`.

`scripts/supervise.sh <home>` is a minimal supervisor that does exactly the table above. With
systemd, the equivalent is a service that restarts on exit plus a timer that kills a stalled loop.
Those units are in [`deploy/systemd/`](deploy/systemd/), and [SERVER.md](SERVER.md) installs them
under a dedicated user.

**What is guaranteed, and what it depends on.**

- A queued task is never lost: it is written to `jobs.json` (write-then-rename) before it is
  removed from `tasks.jsonl`. A crash between the two duplicates the row, and the duplicate is
  dropped by id. This depends on the filesystem honouring rename atomically (local disks do;
  some network filesystems do not).
- A job that finished is not run again: on recovery its journal entry is checked first.
- A replayable job interrupted by a crash runs again (at least once).
- A job that acts on the world is never re-run after an interruption without an approval for that
  attempt (at most once unless the operator says otherwise). Whether it already acted is
  something only the operator can check: the brain cannot see outside itself.
- Restarting after a crash, a hang or a reboot is the supervisor's job (systemd, launchd,
  `supervise.sh`). Recovery itself happens on the next start.
- Connectivity is a guess from cheap probes (a TCP connect to the proxy or provider, an HTTP
  HEAD to the provider, the CLI on PATH). The probes and the CLI can disagree, for example when
  the CLI reaches the provider by a route the probes do not use. The breaker catches that case:
  failed calls close the gate within one call (credentials, overload) or three (anything else).

**The real runs** (2026-10-24, `scripts/recovery_demo.sh`, Haiku 5.5, records in the project
files under `privatebrain-runs/2026-10-24/hardening/`):

1. SIGKILL during a model call on a side-effecting task. The supervisor saw exit 2 within 2 s
   and started a new loop. It raised `crash_recovered`, blocked the task with "interrupted during
   a run that acts on the world" and required approval `retry-after-interrupt-1`. A capability
   task queued alongside it finished. The killed call has a `started` row in the ledger and no
   finished row, so `status` reports "1 killed call charged at its cap" ($0.10).
2. The operator approved once; a second `approve` said "already approved" and added nothing.
   The task ran once.
3. SIGSTOP on the loop. `health` turned to exit 1 after 31.7 s (stale after 30 s); the
   supervisor SIGKILLed it and started another, which recovered.
4. After both restarts, every job reached `done` exactly once (`task_done` per job: max 1).

## Evidence

**Tests.** `tests/test_substrate.py` has 13 offline tests, and `tests/test_boundary.py` adds one
test per risk found in the hardening pass (scoped approvals, bad capability arguments at
execution, the inbox under a crash, failure classification, health, the shared gate).
`tests/test_substrate.py` They use switchable probes and a stub model that counts its calls. They cover:
- offline known work, memory, waiting and blocking, with zero model calls;
- reconnecting, reconciling, then recalling the model's output once offline again;
- the degraded mode;
- crash recovery, and holding interrupted side effects for approval;
- the bound on crash loops;
- backoff and the breaker;
- network loss in the middle of a call;
- a tampered floor;
- validating model proposals;
- deadlines and recurring jobs;
- the single-loop lock;
- the budget;
- the low-resource event.

**A real disconnected run** (2026-10-24, `scripts/offline_demo.sh`). The offline phases run inside
`unshare -rn`, a network namespace with no interfaces, so no proxy, provider or DNS is
reachable. The online phases use Haiku 5.5 through the sandboxed executor. The full log and brain
home are in the project files under `privatebrain-runs/2026-10-24/substrate-offline-demo/`.

1. **Online, then killed.** A model task started, and the process got SIGKILL during the call.
2. **Offline.** On restart:
   - `crash_recovered` fired (the last heartbeat was written as the task started, just before the kill), and the interrupted task was requeued.
   - The connectivity sense reported `network_unavailable`, and the mode went online → offline.
   - Of 10 jobs, 4 finished: an exact money total (113.90 GBP, within the 120 budget), a calendar clash found, the boiler engineer's name recalled from `notes/house.md`, and "I have nothing recorded about 'my passport renewal'".
   - 4 waited for `remote_model`, 1 failed as `unknown` (`stocks.buy`), and 1 was blocked on `calendar-access`.
   - An overdue deadline raised `task_overdue`.
   - **Model calls in this phase: 0.**
3. **Online again.** The operator satisfied `calendar-access`. The next run raised `remote_model_available` and reconciled all 5 parked or blocked jobs, and all 5 finished. The landlord email came back as a draft: the executor has no tools, and the model said so.
4. **Offline again.** A recall query found the model's answer from phase 3 at the top, with no model running.

Cost of the whole run: 5 completed model calls, $0.0026.

## What this does not show yet

- **No local model (level 3).** Natural-language requests that match no rule still wait for the remote model.
- **Rules cover few tasks.** One pure route, one mixed route, three capabilities and retrieval. Most free-text work still needs a model.
- **Fixed since the first run.** The budget route now reads number words ("two radiator valves at
  14.20 each" computed 31.90 GBP with one interpretation call in the 2026-10-24 rerun), and declines
  a quantity that is not a whole number (probably swapped with the price) or a line that may state a
  line total ("3 tickets, 90 in total"). A killed model call now leaves a `started` row.
- **A killed call's cost is unknown.** It is charged at its cap, which overstates it (Haiku calls
  cost about $0.001 against a $0.10 cap); `status` says how many such calls there are.
- **One job per tick.** Jobs run synchronously, so a slow model call delays the senses until it
  returns. That call is bounded by `--timeout`, and `health` treats it as busy, not hung, until then.
- **The v0 `tick`.** It now works with no tools by default and skips work while a `run` loop holds
  the queue. Its tool-using executor and harness² improver need `--allow-unconfined` (DESIGN.md).
- **Not an OS sandbox.** The boundary is that no unattended model has tools (`llm.call`), plus the
  checks above. Another program running as the operator's user can still write any file in the
  brain home. [SERVER.md](SERVER.md) runs the brain as its own user, which keeps the operator's
  other programs out; making `FLOOR.md` and `approvals.jsonl` owned by the operator and read-only
  to the brain, so the floor is an OS-enforced boundary, is still not set up.
