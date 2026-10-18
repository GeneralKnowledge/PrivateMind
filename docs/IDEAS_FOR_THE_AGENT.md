# Ideas for the agent (optional, not a roadmap)

PrivateMind’s operator bootstraps **trust floors** (vault, protected paths, no auto-merge to `main`, verification for workers). After that, **you** choose what to improve. This file is a suggestion box — not requirements, not tickets, not promises.

**Free-tier stack research:** [FREE_TIER_RESEARCH.md](FREE_TIER_RESEARCH.md) — provisional notes on $0 services (LLM, git, VMs, webhooks). Validate limits before building on them.

**Hidden / cheap infra:** Extend [FREE_TIER_RESEARCH.md](FREE_TIER_RESEARCH.md) and [FREE_TIER_CANDIDATES.md](FREE_TIER_CANDIDATES.md) when you discover under-advertised allowances (Kaggle GPU hours, **NVIDIA NIM** hosted + self-hosted, Modal **$30/mo**, codelab credits, Paperspace, IONOS intro VPS, etc.).

**Probe before adopting:** `privatemind research probe-api` / `probe-nim`, then `research candidate --verdict useful|reject` with evidence. Use the **GPU spillover ladder** in the research doc — don’t run batch training on the brain VM.

**GitHub lists:** Run `privatemind research github-sync` against [data/free_tier_github_sources.json](data/free_tier_github_sources.json); add catalog rows for gaps, then verify with probes — never trust README limits without a dated check.

**October 2026 catalogue:** Maintain [FREE_TIER_CATALOG_OCT2026.md](FREE_TIER_CATALOG_OCT2026.md) and [data/free_tier_entitlements.json](data/free_tier_entitlements.json) — Category A/B/C, official vs enforced limits, UK/card/commercial fields. Discovery via freellm.net is not proof. SambaNova = C until probe beats 402; UnoRouter = aggregator C; GitHub Models = retired.

Pick what fits evidence and risk. Record limitations when something is out of scope. Prefer changes that come with tests and honest `docs/STATUS.md` updates.

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
