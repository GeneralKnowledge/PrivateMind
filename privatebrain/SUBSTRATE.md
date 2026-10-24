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
`Substrate.propose`, which validates the fields and stamps the job `origin: "model"`. Model
work runs through `llm.call` with no tools. Approvals come from the operator's `approvals.jsonl`,
which the loop reads and never writes.

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

   Safety checks run first. The job is marked running and saved before it runs.
6. **Vitals.** The reading, the job counts and a heartbeat go to `vitals.json`, so an external supervisor can watch the heartbeat.

The loop behaves differently depending on why something cannot proceed:

| Situation | What happens |
|---|---|
| Remote model unreachable | Model jobs go to `waiting` for `remote_model`. Everything else carries on. |
| A model call fails and the network is down | The job goes to `waiting`. The attempt is not counted against it. |
| A model call fails and the network is up | Retried with exponential backoff, at most 3 attempts. After 3 consecutive failures the breaker opens for 5 minutes, then half-opens. |
| A job requires a need that is not satisfied | The job is `blocked` and the need is recorded for the next batched ask. It runs once the operator satisfies the need. |
| A capability that does not exist | `failed`, kind `unknown`. This means *I do not know how*, which is different from `waiting`, *I cannot do this right now*. |
| Bad input to a capability | `failed`, kind `bad_input`. Not retried. |
| A crash (SIGKILL) during a run | The next start sees the stale lock and raises `crash_recovered`. A replayable job is requeued, with at most 3 interruptions before it fails. A side-effecting job is `blocked` for approval, because it may already have acted. |
| A side-effecting job proposed by a model | `blocked` until `privatebrain approve <id>`. |
| Today's model spend reaches `PRIVATEBRAIN_DAILY_BUDGET_USD` (default $1) | Model jobs wait for `model_budget`. |
| Storage not writable | Every job waits, because results could not be kept. |

Only one loop runs at a time: the lock file holds its pid. Every state change is an event in
`events.jsonl`, which is append-only. Here is an event from the run below:

```json
{"type": "remote_model_unavailable", "timestamp": "2026-10-24T13:58:39+00:00", "severity": "warning",
 "source": "connectivity", "affected_capability": "remote_reasoning", "reasons": ["network_unavailable"]}
```

## Evidence

**Tests.** `tests/test_substrate.py` has 13 offline tests. They use switchable probes and a stub model that counts its calls. They cover:
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
- **One failure seen in the run.** The mixed budget route declined "two radiator valves at 14.20 each", because the quantity is a word ("two"), and the task fell back to a full model call. The answer was right, but it cost a call that code could have saved.
- **A killed model call leaves no ledger row.** `llm.call` writes its row after the call returns, so the call in phase 1 has no recorded cost.
- **No supervisor ships with it.** Recovery happens on the next start. Restarting the process after a crash is the job of systemd, launchd or similar, which can also watch the `vitals.json` heartbeat.
- **One job per tick.** Jobs run synchronously, so a slow model call delays the senses until it returns. That call is bounded by `--timeout`.
- **The v0 `tick` is unchanged.** `privatebrain tick` and `privatebrain run` read the same queue, so use one or the other. The v0 tick's floor gaps listed in DESIGN.md still apply to it.
