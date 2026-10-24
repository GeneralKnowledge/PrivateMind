# PrivateBrain

A persistent agent whose **mind is an editable harness** (prompts, guardrails,
memory, tool guidance, skills, subagents, scripts, plugins) and which **improves
that mind itself** with [harness²](https://github.com/GeneralKnowledge/harness2)'s
Propose–Probe–Compose recursion, above an operator **floor** it cannot edit.

This is a fresh rebuild of the PrivateMind concept, not a port of its code. Read
[DESIGN.md](DESIGN.md) for how the needs / executive / floor layers map onto it.

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

v0. The offline loop is tested end to end. Runs against real models have not been
exercised yet; expect to tune the executor's allowed tools and timeouts.
