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

## Install

Python 3.12 or 3.13, plus the [Claude Code CLI](https://docs.claude.com/en/docs/claude-code)
for the default executor and improver.

```bash
cd privatebrain
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -e '.[dev]'
pytest -q            # offline: scripted agent + scripted editor, real harness² recursion
```

## Use

```bash
privatebrain init                         # ~/.privatebrain (or --home / PRIVATEBRAIN_HOME)
$EDITOR ~/.privatebrain/FLOOR.md && privatebrain floor accept

privatebrain task "Summarise this week's arXiv papers on agent memory" --domain research
privatebrain task "Email the landlord about the boiler" --domain admin --side-effects
privatebrain tick --steps 5               # work -> ask -> improve -> reflect
privatebrain status
privatebrain mind log                     # every adopted mind, with its evidence
privatebrain mind rollback 0
```

Graded experiments and compute-first routing (see [DESIGN.md](DESIGN.md) and [EXPERIMENTS.md](EXPERIMENTS.md)):

```bash
privatebrain experiment run --budget 60 --repeats 3   # baseline, GEPA candidate, keep or reject
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
privatebrain approve <job>                        # the safety layer reads approvals; models cannot write them
scripts/offline_demo.sh /tmp/pb-demo              # the real disconnected run (Linux, unshare -rn)
```

| Setting | Meaning |
|---|---|
| `ANTHROPIC_API_KEY` (or a logged-in `claude`) | Credentials for both the agent and the improver |
| `PRIVATEBRAIN_MODEL` | Model for doing tasks (CLI default if unset) |
| `PRIVATEBRAIN_IMPROVER_MODEL` | Model for harness² editing and selection, and GEPA reflection (default `claude-opus-5-5`) |
| `PRIVATEBRAIN_EVAL_MODEL` | Model the mind runs on in experiments (default `claude-haiku-5-5`) |
| `privatebrain mind auto-adopt off` | Queue improvements for `mind approve <episode>` instead of adopting them |

Tasks marked `--side-effects` are journaled but never replayed, because harness²
improves a mind by re-running the same task several times.

## Status

The graded experiment loop and compute-first routing have run against a real model
(Haiku 5.5 doing the tasks, Opus 5.5 reflecting for GEPA). In total: 219 model calls,
$0.41, and one mind change adopted, with held-out going from 0.43 to 1.00. One change was
rejected as within noise. [EXPERIMENTS.md](EXPERIMENTS.md) has the numbers and what they do
and do not show. The v0 tick (`privatebrain tick`, with the agentic executor and harness²
improve) has still not run against a real model.
