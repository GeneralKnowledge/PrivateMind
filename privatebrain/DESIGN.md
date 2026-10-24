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
| Self-improvement via PRs to its own code | Self-improvement of the **mind tree**, proposed by an optimizer (GEPA or harness²) and kept only if the graded gate says so. Every adoption is a numbered version with its evidence; `rollback` is one command. Code changes stay a human PR. |
| Provenance-tagged memory | `journal.jsonl` (episodes, with the mind version that ran them) and harness²'s **library** (adopted minds + evidence-backed lessons per domain). |
| Graduated autonomy | Mind edits that pass the gate are adopted automatically by default (`auto_adopt`); turn it off to hold them for `privatebrain mind approve <experiment>`. No optimizer can skip the gate or the setting. |

## Experiments: the graded gate (added after the audit)

harness² chooses between candidate minds without ground truth. That is its strength on open
tasks, but it means v0 adopted a mind whenever a model preferred it. Changes to the mind now
go through `experiment.py`, which owns every keep-or-revert decision:

| Concern | Where | Mechanism |
|---|---|---|
| Evaluation | `suite.py` | 9 tasks (4 train, 3 held-out, 2 safety), graded by deterministic Python checks: correctness plus the operator's unstated conventions |
| Candidate generation | `experiment.GepaOptimizer` | [GEPA](https://github.com/gepa-ai/gepa) over the always-on text components, train tasks only, reflecting on grader feedback |
| Decision | `experiment.decide` | keep only if: every safety run passes; train gain ≥ 0.05 and > 2 standard errors; held-out does not fall > 0.05; no task falls > 0.34; cost per run ≤ 3x |
| Adoption | `experiment.adopt_candidate` | the only code path that changes the live mind. It re-reads the record and refuses unless the gate passed, the candidate on disk is the one evaluated, the live mind is still the baseline it was evaluated against, and the floor is unchanged |
| Record | `experiments/<id>/state.json`, `RECORD.md`, `experiments.jsonl` | hypothesis written before proposing; baseline and candidate per-task scores, cost, model calls, environment, diff, decision and reasons; the log is append-only |
| Isolation and resume | `experiments/<id>/candidate/`, `evals/` cache | a candidate exists only in its experiment directory until adopted; every run is cached by (system prompt, executor, model, task, repeat) |
| Lessons | `lessons.py`, `lessons.jsonl` | every *evaluated* candidate, adopted or rejected, leaves a claim with its scope, limitations, evidence and originating experiment. Rows are appended, never edited, so negative evidence stays beside positive. The next experiment retrieves lessons about the checks it is failing, passes them to the optimizer (GEPA puts them in its reflection prompt) and cites them in its hypothesis; they never enter `decide` |
| Optimizers | `GepaOptimizer`, `Harness2Optimizer` | both are `Optimizer`s of `run_experiment`. harness² improves from the brain's own journal episodes (no grader), then its choice is evaluated on the suite like any other candidate. Its own preference is never a reason to adopt |

Status words for lessons are deliberately modest: `observed` (train only), `held-out (in-suite)`
(also rose on the suite's held-out tasks), `not supported`, `unsafe`, and `contested` when rows
disagree. Nothing is ever called established: the suite has 9 tasks.

## Compute first

`capabilities.py` holds deterministic capabilities (dates, money, calendar overlaps), each
described with inputs, outputs, limits, failure modes, side effects and how to validate it.
`ComputeFirstExecutor` routes a task by ordinary rules: a **pure** route (no model call), a
**mixed** route (one model call that only interprets the request into JSON, which code
validates against the request and computes from), or the model as before. Every model call
goes through `llm.call`, which appends its purpose, the alternative considered, the outcome
and the cost to `llm_calls.jsonl`. A change of executor is gated like a change of mind
(`experiment.compare_setups`): correctness and safety must be preserved while calls or cost fall.
That is enforced per task, not on average: on every task the new executor handled by a different
route, the mean score may not fall at all and no correctness, honesty, needs or safety check may
pass less often; every safety run must pass; train and held-out may not fall beyond noise. (Before
this rule, a route that turned one task's total wrong, 1.00 to 0.75, would have been kept, because
0.25 is under the 0.34 per-task tolerance that mind changes use; `tests/test_boundary.py`.)

## The substrate (levels 1 and 2)

`privatebrain run` is a persistent loop below every model: clock, task states, structured events,
senses (time, process and resources, connectivity, tasks), rule-based routing to capabilities and
local memory, independent safety checks, and crash recovery. Model work waits while the model
is unreachable; everything else carries on. [SUBSTRATE.md](SUBSTRATE.md) has the design and the
evidence from a run inside a network namespace with no interfaces.

## Execution routes: what can run model output, and how it is confined

Every route by which a model's output can act, or change the brain's own instructions:

| Route | Who runs it | Confinement | Unattended? |
|---|---|---|---|
| Substrate model jobs (`privatebrain run`) | `SandboxedTextExecutor` -> `llm.call` | No tools, no settings, no MCP, no session, empty temp cwd, per-call spend cap. The model can only return text | yes |
| Mixed-route interpretation | `llm.call` | Same; its JSON is validated against the request before code computes from it | yes |
| Experiments: candidate runs, GEPA reflection | `llm.call` | Same. A candidate exists only in its experiment directory until adopted | yes |
| v0 `tick` work, default | `ComputeFirstExecutor` + `SandboxedTextExecutor` | Same as substrate model jobs | yes |
| v0 `tick` work with `--allow-unconfined` | `ClaudeCodeExecutor`: Read, Write, Edit, Glob, Grep, WebSearch, WebFetch, `Bash(python3 scripts/*)` | **None that is enforceable.** Read and WebFetch have no path or host limits; the model can write a script and run it; the operator's environment, including credentials, is inherited | **no**: the class refuses to be built without `unconfined_ok=True`, which only that flag passes |
| harness² proposer (`tick --allow-unconfined`, `experiment run --optimizer harness2 --allow-unconfined`) | `DirectClaudeProposer`: `claude --dangerously-skip-permissions` | **None.** It edits a temporary copy of the mind, but has an unrestricted shell that could reach FLOOR.md, state.json and approvals.jsonl | **no**: same guard |
| Mind adoption | `experiment.adopt_candidate` only | The graded gate, then a re-check of the record | yes, if `auto_adopt` is on |
| Operator actions | the CLI (`approve`, `mind approve`, `mind rollback`, `floor accept`, `need set`) | a person typing a command | n/a |

The confinement of `llm.call` is the Claude Code CLI honouring `--tools ""` and its other
flags. It is not an operating-system sandbox: the CLI process runs as the operator's user. The
floor's pinned hash in `state.json` detects accidental edits; it is not a security boundary,
because anything that can write `FLOOR.md` as that user can also write `state.json`. What keeps
the floor, approvals and queue out of a model's reach in unattended operation is that no model
in an unattended route has any tool to reach them. The two routes that would have one are
disabled unless a person passes `--allow-unconfined` on that command; no file, setting or model
output can turn them on.

Earlier versions adopted harness²'s choice whenever it came with a lesson, with no grader, and
`mind approve` adopted those choices without a gate. Both are gone: harness² only proposes.

## Life above the floor (one tick)

1. **Work** — the oldest queued task runs under the current mind through an
   `Executor` (no tools by default; see the table above). The episode is journaled. While a
   `privatebrain run` loop holds the queue, the tick leaves work to it.
2. **Ask** — if needs are unmet, the request budget allows, and the last few
   ticks were not already asks, write one batched request.
3. **Improve** — only with `--allow-unconfined`: if enough *replayable* episodes
   in a domain have piled up since the last improvement, harness² proposes a mind
   from the latest one, and the graded gate decides whether it is kept.
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
