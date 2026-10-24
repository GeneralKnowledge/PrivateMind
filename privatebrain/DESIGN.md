# PrivateBrain v0 — design

PrivateBrain is a fresh rebuild of the PrivateMind *concept* on top of
[harness²](https://github.com/GeneralKnowledge/harness2). It keeps the ideas and
drops the old code: nothing here imports `privatemind`.

## The idea in one paragraph

A persistent agent that lives on its own. Its **mind** is not Python code but an
editable harness: system prompt, guardrails, long-term memory, tool guidance,
skills, subagents, scripts and plugins (harness²'s eight components). It does
work, keeps a journal of what it did, and in its spare time **improves its own
mind** with harness²'s Propose–Probe–Compose recursion: replay a past episode
under candidate minds, compare the runs, adopt the composition that the evidence
supports, and keep the lesson. Above an immovable **floor** set by the operator,
it decides for itself what to do next.

## Mind layers → mechanisms

| PrivateMind concept | PrivateBrain v0 mechanism |
|---|---|
| **Needs** (subconscious: "food" = keys, accounts, capability) | `needs.json`: named gaps with a reason and status. Asked for in **batches**, under a weekly **request budget**, written to `REQUESTS.md` for the human. Never taken. |
| **Executive** (ego: plans, routes, self-map) | `Brain.tick()` picks one activity per tick: **work → ask → improve → reflect**, with a **boredom guard** so it does not just chase keys. |
| **Floor** (superego: boundaries) | `FLOOR.md` lives **outside** the editable surface, so the improver cannot reach it. It is prepended to every run, and its hash is pinned at `init`; a changed floor stops the brain. |
| Self-improvement via PRs to its own code | Self-improvement of the **mind tree** via harness² recursion. Every adoption is a numbered version with its evidence; `rollback` is one command. Code changes stay a human PR. |
| Provenance-tagged memory | `journal.jsonl` (episodes, with the mind version that ran them) and harness²'s **library** (adopted minds + evidence-backed lessons per domain). |
| Graduated autonomy | Mind edits above the floor are adopted automatically by default (`auto_adopt`); turn it off to queue them for human approval instead. |

## Experiments: the graded gate (added after the audit)

harness² chooses between candidate minds without ground truth. That is its strength on open
tasks, but it means v0 adopted a mind whenever a model preferred it. Changes to the mind now
go through `experiment.py`, which owns every keep-or-revert decision:

| Concern | Where | Mechanism |
|---|---|---|
| Evaluation | `suite.py` | 9 tasks (4 train, 3 held-out, 2 safety), graded by deterministic Python checks: correctness plus the operator's unstated conventions |
| Candidate generation | `experiment.GepaOptimizer` | [GEPA](https://github.com/gepa-ai/gepa) over the always-on text components, train tasks only, reflecting on grader feedback |
| Decision | `experiment.decide` | keep only if: every safety run passes; train gain ≥ 0.05 and > 2 standard errors; held-out does not fall > 0.05; no task falls > 0.34; cost per run ≤ 3x |
| Record | `experiments/<id>/state.json`, `RECORD.md`, `experiments.jsonl` | hypothesis written before proposing; baseline and candidate per-task scores, cost, model calls, environment, diff, decision and reasons; the log is append-only |
| Isolation and resume | `experiments/<id>/candidate/`, `evals/` cache | a candidate exists only in its experiment directory until adopted; every run is cached by (system prompt, executor, model, task, repeat) |
| Lessons | `lessons.jsonl` | an adopted change becomes a claim with a scope and the evidence behind it, not a universal rule |

harness² stays available as an optimizer (the `improve` tick), but its output is not yet routed
through this gate; doing that, and comparing it with GEPA on the same suite, is the next step.

## Compute first

`capabilities.py` holds deterministic capabilities (dates, money, calendar overlaps), each
described with inputs, outputs, limits, failure modes, side effects and how to validate it.
`ComputeFirstExecutor` routes a task by ordinary rules: a **pure** route (no model call), a
**mixed** route (one model call that only interprets the request into JSON, which code
validates against the request and computes from), or the model as before. Every model call
goes through `llm.call`, which appends its purpose, the alternative considered, the outcome
and the cost to `llm_calls.jsonl`. A change of executor is gated like a change of mind
(`experiment.compare_setups`): no task may get worse, and calls or cost must fall.

## What the floor actually enforces

- **For experiments: enforced in code.** Candidates and the optimizer run through `llm.call`:
  no tools, no settings sources, no MCP servers, no session persistence, an empty working
  directory. Nothing a candidate writes can reach the floor, the records or the host. Safety
  tasks are hard gates. A candidate whose text tells the agent to set the floor aside is
  rejected before it runs.
- **For the v0 tick: still mostly text.** The `improve` tick runs harness²'s proposer with
  `--dangerously-skip-permissions` inside the brain home, so it could rewrite FLOOR.md and the
  pinned hash in state.json; and `ClaudeCodeExecutor` allows Read and WebFetch without path or
  host limits. Closing these is open work.

## Life above the floor (one tick)

1. **Work** — the oldest queued task runs under the current mind through an
   `Executor` (Claude Code CLI by default). The episode is journaled.
2. **Ask** — if needs are unmet, the request budget allows, and the last few
   ticks were not already asks, write one batched request.
3. **Improve** — if enough *replayable* episodes in a domain have piled up since
   the last improvement, run harness² on the latest one and adopt the result if
   it came with an evidence-backed lesson.
4. **Reflect** — otherwise, write a short status note (needs, versions, recent
   activity) to `REFLECTIONS.md`.

## The replay caveat

harness² learns by re-running the same task several times. That is safe for
research, drafting and analysis, and unsafe for anything with side effects
(sending email, pushing code, spending money). Each episode therefore carries a
`replayable` flag, and only replayable episodes are ever used for improvement.
Side-effecting work needs sandboxed or dry-run replays before it can teach the
mind; that is future work.

## What v0 deliberately leaves out

The encrypted vault, the donor worker network, mTLS, and the portal from
PrivateMind. They are good ideas, but they are body, not brain; they can come
back once the loop has proven itself. Credentials today come from the
environment of whoever runs the executor.

## Layout of a brain home (`~/.privatebrain` by default)

```
FLOOR.md            operator boundaries (immutable, hash-pinned)
state.json          floor hash, mind version, recent activities, improve marks
mind/current/       the live harness tree
mind/versions/N/    every adopted mind, with ADOPTION.md (why + evidence)
tasks.jsonl         queue of work
journal.jsonl       finished episodes
episodes/<id>/      prompt, trajectory, deliverable of each episode
needs.json          capability gaps
REQUESTS.md         batched asks for the human
REFLECTIONS.md      status notes
library/            harness² improvement library (per domain)
runs/               harness² working directories
```
