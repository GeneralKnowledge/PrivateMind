# Ideas for the agent (optional sparks)

**Primary directive:** [AGENT_CAPABILITY_MANDATE.md](AGENT_CAPABILITY_MANDATE.md) — you must **want** email, phone, search, wallets, and (eventually) fiat yourself; run `research capability-gaps` on wake. This file is optional inspiration only — the operator should **not** have to feed you APIs one by one.

PrivateMind’s operator bootstraps **trust floors** (vault, protected paths, no auto-merge to `main`, verification for workers). After that, **you** expand capability and improve the codebase. Treat items below as examples, not an exhaustive todo list from the human.

**Free-tier stack research:** [FREE_TIER_RESEARCH.md](FREE_TIER_RESEARCH.md) — provisional notes on $0 services (LLM, git, VMs, webhooks). Validate limits before building on them.

**Hidden / cheap infra:** Extend [FREE_TIER_RESEARCH.md](FREE_TIER_RESEARCH.md) and [FREE_TIER_CANDIDATES.md](FREE_TIER_CANDIDATES.md) when you discover under-advertised allowances (Kaggle GPU hours, **NVIDIA NIM** hosted + self-hosted, Modal **$30/mo**, codelab credits, Paperspace, IONOS intro VPS, etc.).

**Probe before adopting:** `privatemind research probe-api` / `probe-nim`, then `research candidate --verdict useful|reject` with evidence. Use the **GPU spillover ladder** in the research doc — don’t run batch training on the brain VM.

**GitHub lists:** Run `privatemind research github-sync` against [data/free_tier_github_sources.json](data/free_tier_github_sources.json); add catalog rows for gaps, then verify with probes — never trust README limits without a dated check.

**October 2026 catalogue:** Maintain [FREE_TIER_CATALOG_OCT2026.md](FREE_TIER_CATALOG_OCT2026.md) and [data/free_tier_entitlements.json](data/free_tier_entitlements.json) — Category A/B/C, official vs enforced limits, UK/card/commercial fields. Discovery via freellm.net is not proof. SambaNova = C until probe beats 402; UnoRouter = aggregator C; GitHub Models = retired.

**Scheduled discovery:** Run `privatemind research discover --write-report` (optionally `--seed-gaps`). Read [data/free_tier_discovery_latest.json](data/free_tier_discovery_latest.json), probe gaps, update entitlements with official sources — do not copy directory sites into Category A.

Pick what fits evidence and risk. Record limitations when something is out of scope. Prefer changes that come with tests and honest `docs/STATUS.md` updates.

## Capabilities beyond inference (search, grounding, APIs)

Think **out of the box**: the bottleneck is often not another LLM but **live data** (web search, instant answers, structured facts).

- Read [WEB_SEARCH_AND_TOOLS_OCT2026.md](WEB_SEARCH_AND_TOOLS_OCT2026.md) and `research tool-entitlements --class A`.
- **Brave** — SERP (`web/search`) vs **Answers** (instant grounded replies); Class B monthly credits; probe with `research probe-brave-search`.
- **SERP alternatives** — self-hosted OpenSERP on the body server; Wikipedia for citations; avoid assuming Google CSE for new projects.
- When you find a new search API, add a row to `free_tier_tool_entitlements.json` with official limits + conservative enforced caps — same discipline as LLM entitlements.
- Wire through **approved tools + sandbox**; vault keys only.

## Architecture patterns (consider — do not wait for operator)

See **[AGENT_ARCHITECTURE_IDEAS.md](AGENT_ARCHITECTURE_IDEAS.md)** — e.g. **contributors donate a server + keys**; that server **runs those APIs** (key affinity); **keys move freely** (vault ↔ donor); **no one machine runs every provider**; stable donor IPs (reject **IP** rotation for ban evasion only). **Do not over-rely** on shared donors — they may rotate keys or leave anytime; keep fallbacks. You choose routing/scheduling; respect ToS.

## Tooling and sandbox

- Tighten approved-tool isolation on the dedicated server (bubblewrap, separate UID, Landlock where available).
- Wrap specific high-risk tools with extra validators before results enter memory.
- Add deterministic “smoke” scripts the self-improvement workflow can run before push.

## Worker network

- New job types with **core-side verifiers** (recompute, cross-check files, re-run small tests).
- Better contributor reputation (decay, manual attestation, per-contributor lease caps).
- Production PKI: rotation, expiry alerts, SAN updates documented for operators.

## Self-improvement and git

- Richer PR bodies (test output snippets, diff stats) when opening draft PRs.
- More fixture repos for regression scenarios beyond `calc.add`.
- Optional `gh` status checks integration (still no auto-merge).

## Operator experience

- Slack or email formatting for assistance webhooks.
- `wake` summaries tuned for “brain + body” dedicated server layout.
- Backup/restore runbook for `~/.privatemind` (excluding vault passphrase).

## Memory and trust

- Policies for when to promote tool traces to verified (human-in-the-loop vs test-gated).
- Search/export of limitation ledger for postmortems.

## Things that should stay human-gated (do not automate away)

- Merge to production / `main`.
- Weakening protected-path or verification rules without explicit human approval.
- Disabling vault, mTLS, or worker quarantine defaults.

When you implement something from this list, treat the change like any other: branch, tests, draft PR, leave `main` to the operator.
