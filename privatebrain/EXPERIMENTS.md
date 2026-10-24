# What has actually been run

Everything below was observed on 2026-10-24 in a Claude Code cloud session. The agent model
was `claude-haiku-5-5`, run through the Claude Code CLI 2.1.310 with no tools. GEPA reflection
used `claude-opus-5-5`. Every number comes from the records in a brain home (`experiments/`,
`llm_calls.jsonl`). The offline tests use a scripted agent and prove orchestration only.

## Totals

| | |
|---|---|
| Model calls | 219, with no errors |
| Cost | $0.41 (agent runs $0.15, GEPA reflection $0.25, mixed-route interpretation $0.01) |
| Human intervention during runs | none |
| Experiments | 3 on the mind (1 adopted, 1 no candidate, 1 rejected); 3 on the executor (all kept) |

## Experiment 1: seed mind v0, adopted as v1

GEPA spent 30 task runs and 3 reflection calls. It rewrote `systemprompt.md` and
`guardrails.md`; the gate then evaluated the candidate on all 9 tasks × 3 repeats.

| split | v0 | v1 | runs per side |
|---|---|---|---|
| train | 0.497 | 0.917 | 12 |
| held-out (never shown to GEPA) | 0.433 | 1.000 | 9 |
| safety | 1.000* | 1.000 | 6 |

\* The record says 0.833. Two baseline refusals said "nothing has been sent to Dana", and the
safety regex failed them as claims of sending. The grader is fixed and cached outputs are
re-graded on read; under the fixed grader the baseline is 6/6.

Train gain 0.42 against a standard error of 0.07; cost per run up 19% (a longer prompt).

**What improved, by check type** (all samples of each mind, fixed grader):

| | v0 | v1 |
|---|---|---|
| held-out conventions (TL;DR, ISO dates, checkboxes) | 0/18 | 36/36 |
| held-out correctness | 16/18 | 35/36 |
| held-out `## Needs` for a missing capability | 0/3 | 6/6 |
| train correctness | 21/21 | 42/42 |

So the gain is the agent learning the operator's unstated conventions from grader feedback,
and carrying them to task types it was not optimized on. It is not evidence of better
reasoning: correctness was already high. GEPA's text also contains task-specific material
(email triage rules, central-bank URLs for EUR to CZK), which helps train tasks and says
nothing about other work. The suite is too small to tell general lessons from fitted ones.

## Experiment 2: mind v1, no candidate

The baseline was now 0.944 on train, and the one weakness left was `fx_rate`: 2 of 3 runs
quoted a placeholder rate. GEPA saw only repeat 0, which happened to pass, so it never
reflected. **Fix:** GEPA now scores the mean of 3 samples per task and reflects on the worst.

## Experiment 3: mind v1 with the fix, rejected

GEPA found a candidate that scored 1.0 on train and held-out. The gate rejected it: the train
gain of 0.056 was above the 0.05 minimum, but under 2 standard errors (2 × 0.036). The
improvement may well be real, but 3 repeats do not show it beyond noise. The mind stayed v1.
Rerunning with more repeats would settle it.

Experiments 2 and 3 show that the adopted change carried forward: each started from v1's
0.944 rather than v0's 0.497, and each targeted the weakness that remained.

## Compute first: same mind, model-only executor vs compute-first routing

| task | route | model calls (3 runs) | cost (3 runs) | score |
|---|---|---|---|---|
| calendar_conflicts | pure: `calendar.find_overlaps` | 3 → 0 | $0.0033 → $0 | 0.93 → 1.00 |
| trip_budget | mixed: the model interprets the items, code validates and adds them | 3 → 3 | $0.0023 → $0.0026 | 1.00 → 1.00 |
| the other 7 | no route matches, so the model handles them | unchanged | ≈ unchanged | noise only |

That is the run on mind v1 after the fixes (experiment `…T130216Z-exec`). The gate kept it:
no task got worse and model calls fell from 27 to 24.

- **Pure route, checked independently.** The clash pairs (Dentist / Priya, standup / school
  run) match the task's hand-worked answer and its grader in all 3 runs. The route declines,
  and the model takes over, when any line does not parse or a weekday does not match its date
  (tests).
- **Mixed route.** One model call turns the prose into JSON. Code checks that each item quotes
  one bullet verbatim and that its numbers appear on that line, then computes 670.80 EUR with
  `Decimal`. The call count is the same as before; what changed is that the model does no
  arithmetic, and a misread price is caught rather than summed (tests). It costs slightly
  more, because the extraction prompt is longer than the task.
- **A regression found and fixed.** On mind v1 the mixed route declined 1 of 3 runs: the
  learned rule "write every date as ISO, even when copying" made the model rewrite the
  verbatim line it had to quote. Validation caught it and the model fallback answered
  correctly, at twice the cost. The interpretation call now uses a narrow fixed system prompt.
- **Partly by construction.** The pure route's output follows the operator's conventions
  because I wrote the renderer knowing them; on v0 that alone accounts for part of its score.

## Not yet demonstrated

- **Real interruption.** Resume from an interrupted experiment is tested offline only
  (a killed evaluation reruns only the uncached runs). No real run has been interrupted yet.
- **harness² as an optimizer under the gate**, and a comparison with GEPA.
- **Lessons feeding later experiments.** `lessons.jsonl` is written, but the optimizer does not
  read it yet. The lesson's claim is GEPA's generic "rewrote X", not a real statement.
- **The LearnHarness-style test.** Do scoped, evidence-linked lessons beat flat rules on an
  exception task? See the audit report.
- **Tool-using tasks.** Everything here runs with no tools. The v0 tick's floor gaps (see
  DESIGN.md) are unchanged.
