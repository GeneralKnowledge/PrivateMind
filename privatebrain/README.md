# PrivateBrain

**A persistent personal agent that keeps running without a model, learns only from evidence, and
never crosses its owner's floor.**

PrivateBrain runs as a loop on your machine. It keeps a clock and a journal, watches its own
health and connectivity, and does what it can with ordinary code: exact sums, calendar clashes,
searching what it has stored. Work that needs a language model waits honestly while the model
is unreachable ("I can't do this right now"), which is different from work it has no way to do
("I don't know how"). When the model comes back, the waiting work runs, and the results become
memory it can search offline.

Its **mind** is not code but an editable harness (system prompt, guardrails, long-term memory,
tool guidance, skills). It improves that mind in experiments: propose a change, grade it on
fixed tasks with deterministic checks, keep it only if it helps without breaking safety, and
record why. Above an operator **floor** it cannot edit, it decides for itself what to do next,
and it asks for new capabilities rather than taking them.

This is a fresh, small rebuild of the [PrivateMind](../README.md) concept, not a port of its code.

| Read | For |
|---|---|
| [DESIGN.md](DESIGN.md) | How the needs, executive and floor map onto the code |
| [SUBSTRATE.md](SUBSTRATE.md) | The offline loop, senses and safety layer, and the disconnected run |
| [EXPERIMENTS.md](EXPERIMENTS.md) | The graded self-improvement gate and what real-model runs showed |
| [SERVER.md](SERVER.md) | Running it on a server: dedicated user, systemd service, watchdog, credentials, health |

## Install

**On a server**, follow [SERVER.md](SERVER.md): it sets up a dedicated user, a systemd service
that restarts a dead or hung loop, and a `pb` wrapper for daily commands.

**For development**: Python 3.12 or 3.13 and `git`. The
[Claude Code CLI](https://docs.claude.com/en/docs/claude-code) is optional; every model call goes
through it (with no tools unless you say otherwise; see
[DESIGN.md](DESIGN.md#execution-routes-what-can-run-model-output-and-how-it-is-confined)), and
without it the brain still runs and model work waits.

```bash
git clone https://github.com/GeneralKnowledge/PrivateMind.git && cd PrivateMind/privatebrain
python3 -m venv .venv && source .venv/bin/activate   # or: uv venv --python 3.12 .venv
pip install -e '.[dev]'
pytest -q            # offline: scripted agent + scripted editor, real harness² recursion
```

Credentials for model work: `ANTHROPIC_API_KEY`, a `CLAUDE_CODE_OAUTH_TOKEN` from
`claude setup-token`, or a logged-in `claude`.

## Use

```bash
privatebrain init                         # ~/.privatebrain (or --home / PRIVATEBRAIN_HOME)
$EDITOR ~/.privatebrain/FLOOR.md && privatebrain floor accept

privatebrain task "Summarise this week's arXiv papers on agent memory" --domain research
privatebrain task "Email the landlord about the boiler" --domain admin --side-effects
privatebrain tick --steps 5               # work -> ask -> reflect, with no tools
privatebrain tick --allow-unconfined      # attended only: tool-using executor and harness² improver, NOT sandboxed
privatebrain status                       # running? heartbeat? online? budget? jobs, approvals, mind
privatebrain mind log                     # every adopted mind, with its evidence
privatebrain mind rollback                # back to the version that was live before (or: rollback <n>)
```

Graded experiments and compute-first routing (see [DESIGN.md](DESIGN.md) and [EXPERIMENTS.md](EXPERIMENTS.md)):

```bash
privatebrain experiment run --budget 60 --repeats 3   # baseline, GEPA candidate, keep or reject
privatebrain experiment run --optimizer harness2 --domain writing --allow-unconfined  # harness² proposes, same gate
privatebrain experiment lessons                       # what earlier experiments found, with evidence and limits
privatebrain mind approve <experiment-id>             # with auto-adopt off: adopt a candidate that passed the gate
privatebrain experiment compare-executors             # model-only vs compute-first, same gate
privatebrain experiment log                           # every experiment, append-only
privatebrain experiment show <id>                     # one record: hypothesis, scores, diff, decision
privatebrain capabilities                             # the deterministic capabilities and their limits
```

An interrupted `experiment run` resumes where it stopped: finished task runs are cached.

The substrate loop keeps the brain working with no model reachable (see [SUBSTRATE.md](SUBSTRATE.md)):

```bash
privatebrain run                                  # persistent loop: senses, safety, known work, recovery
privatebrain run --offline --until-idle           # as if the remote model were disconnected
privatebrain task "" --capability money.sum_line_items --args '{"items": [...], "currency": "EUR"}'
privatebrain task "What do you know about the boiler?"   # answered from local memory (BM25)
privatebrain task "Weekly review" --every 604800 --deadline 2026-11-01T09:00:00+00:00
privatebrain senses                               # one reading: clock, process, resources, connectivity, tasks
privatebrain jobs                                 # each job's state and why it waits or is blocked
privatebrain events --tail 20                     # the structured event journal
privatebrain recall "boiler engineer"             # memory search, no model
privatebrain approve <job>                        # approves what the job is blocked on now, once
privatebrain health                               # for a supervisor: exit 0 healthy, 1 stalled, 2 not running
scripts/supervise.sh ~/.privatebrain              # a minimal supervisor: restarts a dead or stalled loop
scripts/offline_demo.sh /tmp/pb-demo              # the real disconnected run (Linux, unshare -rn)
scripts/recovery_demo.sh /tmp/pb-recovery         # SIGKILL and SIGSTOP under the supervisor
```

| Setting | Meaning |
|---|---|
| `ANTHROPIC_API_KEY` (or a logged-in `claude`) | Credentials for both the agent and the improver |
| `PRIVATEBRAIN_MODEL` | Model for doing tasks (CLI default if unset) |
| `PRIVATEBRAIN_IMPROVER_MODEL` | Model for harness² editing and selection, and GEPA reflection (default `claude-opus-5-5`) |
| `PRIVATEBRAIN_EVAL_MODEL` | Model the mind runs on in experiments (default `claude-haiku-5-5`) |
| `PRIVATEBRAIN_DAILY_BUDGET_USD` | Model spend per day before model work waits (default 1.0) |
| `PRIVATEBRAIN_CALL_CAP_USD` | Spend cap per substrate model call; a call killed mid-flight is charged at it (default 0.10) |
| `privatebrain mind auto-adopt off` | Hold candidates that pass the gate for `mind approve <experiment>`; also stops `compare-executors` switching the executor |

Tasks marked `--side-effects` are journaled but never replayed, because harness²
improves a mind by re-running the same task several times.

## Status

The graded experiment loop and compute-first routing have run against a real model
(Haiku 5.5 doing the tasks, Opus 5.5 reflecting for GEPA). In total: 219 model calls,
$0.41, and one mind change adopted, with held-out going from 0.43 to 1.00. One change was
rejected as within noise. [EXPERIMENTS.md](EXPERIMENTS.md) has the numbers and what they do
and do not show. The substrate's offline and recovery behaviour has been run for real: see
[SUBSTRATE.md](SUBSTRATE.md). harness² now proposes under the same gate as GEPA, but that path
(which needs `--allow-unconfined`) has only been tested offline with a scripted editor.
