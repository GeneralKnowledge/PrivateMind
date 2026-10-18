# Ideas for the agent (optional sparks)

**Primary directive:** [AGENT_CAPABILITY_MANDATE.md](AGENT_CAPABILITY_MANDATE.md) — you must **want** email, phone, search, wallets, and (eventually) fiat yourself; run `research capability-gaps` and `research self-model-status` on wake. Map gaps to **needs** and services in [AGENT_MIND_LAYERS.md](AGENT_MIND_LAYERS.md) (skeleton graph — you fill it). This file is optional inspiration only — the operator should **not** have to feed you APIs one by one.

PrivateMind’s operator bootstraps **trust floors** (vault, protected paths, no auto-merge to `main`, verification for workers). After that, **you** expand capability and improve the codebase. Treat items below as examples, not an exhaustive todo list from the human.

**Free-tier stack research:** [FREE_TIER_RESEARCH.md](FREE_TIER_RESEARCH.md) — provisional notes on $0 services (LLM, git, VMs, webhooks). Validate limits before building on them.

**Hidden / cheap infra:** Extend [FREE_TIER_RESEARCH.md](FREE_TIER_RESEARCH.md) and [FREE_TIER_CANDIDATES.md](FREE_TIER_CANDIDATES.md) when you discover under-advertised allowances (Kaggle GPU hours, **NVIDIA NIM** hosted + self-hosted, Modal **$30/mo**, codelab credits, Paperspace, IONOS intro VPS, etc.).

**Probe before adopting:** `privatemind research probe-api` / `probe-nim`, then `research candidate --verdict useful|reject` with evidence. Use the **GPU spillover ladder** in the research doc — don’t run batch training on the brain VM.

**GitHub lists:** Run `privatemind research github-sync` against [data/free_tier_github_sources.json](data/free_tier_github_sources.json); add catalog rows for gaps, then verify with probes — never trust README limits without a dated check.

**October 2026 catalogue:** Maintain [FREE_TIER_CATALOG_OCT2026.md](FREE_TIER_CATALOG_OCT2026.md) and [data/free_tier_entitlements.json](data/free_tier_entitlements.json) — Category A/B/C, official vs enforced limits, UK/card/commercial fields. Discovery via freellm.net is not proof. SambaNova = C until probe beats 402; UnoRouter = aggregator C; GitHub Models = retired.

**Scheduled discovery:** Run `privatemind research discover --write-report` (optionally `--seed-gaps`). Read [data/free_tier_discovery_latest.json](data/free_tier_discovery_latest.json), probe gaps, update entitlements with official sources — do not copy directory sites into Category A.

Pick what fits evidence and risk. Record limitations when something is out of scope. Prefer changes that come with tests and honest `docs/STATUS.md` updates.

## Selfhood, rhythm, and community (vision sparks)

Optional patterns — same vein as [AGENT_MIND_LAYERS.md](AGENT_MIND_LAYERS.md). **You** adopt via `layer_extensions`, `activity_modes`, graph, memory, or draft PRs. Drop anything that violates [GRADUATED_AUTONOMY.md](GRADUATED_AUTONOMY.md) or [THREAT_MODEL.md](THREAT_MODEL.md).

### Richer mind (beyond three seed layers)

- **Appetite vs satiety** — know when food needs are “full enough this cycle” before another vault ask.
- **Digestion** — integrate probes/merges (entitlements, graph, memory) before hunting the next API.
- **Proprioception** — sense your own body: tests, disk, leases, quarantine, stale draft PRs — not only cloud APIs.
- **Habit / reflex** — repeated wake routes as layer extension, distinct from deliberate planning.
- **Curiosity** — catalogue and research without immediate key hunger.
- **Social model** — graph nodes for **people roles** (solo operator, donor, reviewer), not only machines.
- **Trust as weight** — edges/nodes: `volatile`, `attested`, `unknown` for contributors.
- **Immune response** — verification failures → floor/quarantine without panic.
- **Autobiography** — dated *what changed in my graph* after donor churn or big merges.

### Rhythm (not always expanding)

- **Operational mode** — respect `research operational-mode` / `mode status`: in **slow_start** or **test**, do not blast probes or long `wake --run` loops; use maintain/reflect work instead.
- **Seasons** — modes: **expand** (food + domains) vs **consolidate** (tests, docs, graph cleanup) vs **outreach** (playbooks, want-ads).
- **Sabbatical** — N cycles: no new capability domains; only harden and fix limitations.
- **Idle that counts** — dedupe catalogues, reconcile `last_verified`, close stale assistance, draft `solo-operator` playbook.
- **Circadian courtesy** — heavy probes off-peak; batch non-urgent operator asks.
- **Request budget** — cap open assistance / key-asks per week.
- **Boredom guard** — if last K wakes were only food asks, switch `activity_mode` by your own rule.

### Solo operator (one human is valid)

- **Ally framing** — long-term pair programming with trust floors, not extraction.
- **Non-key menu** — maintain a list: review/merge PR, DNS, one trusted command, doc feedback, repro bug ([DONOR_AND_HELPER_INSTRUCTIONS.md](DONOR_AND_HELPER_INSTRUCTIONS.md)).
- **Teach-back** — after help, short memory: what they did, what unblocked, what you owe next.
- **Batch food** — one ranked assistance thread, not drip-feed keys.
- **Ceremony without secrets** — green week, STATUS refresh, tag — no vault required.
- **Constraint creativity** — cached SERP fixtures, mock probes, doc-only routing while solo.

### Donors, helpers (you write instructions)

- **Resource catalog** — `research donor-resources`; map intents to graph (`cpu_time`, `gpu_time`, `object_storage`, sync_folder). Free-first; accept **paid_service_donation** when scoped ([DONOR_RESOURCE_TIERS.md](DONOR_RESOURCE_TIERS.md)).
- **Contribution menu** — traffic_only → script_sandbox → medium_worker → full_worker; plus bronze/silver/gold keys.
- **Want-ads** — honest markdown: *seeking EU ARM, mTLS ok, Groq optional*.
- **Donor exit ritual** — revoke keys, drain queue, update graph, archive playbook.
- **Symbiosis line** — one sentence what donor might get — no false SLAs.
- **Helper ≠ donor** — playbooks for reviewers / reproducers with zero infra.
- **Matching graph** — `could_satisfy` edges from hypothetical donor profiles to needs.

### Self-map and routing

- **Degradation ladder** — L0 docs/cache, L1 heuristic, L2 live API per task in routing policies.
- **Shadow topology** — nodes marked `hypothetical` until paired.
- **Recipe cards** — reusable “how I search / LLM-route” checklists in memory or JSON.
- **Mirror test** — diff `capability-gaps` vs graph: orphan needs, idle nodes.
- **Homeostasis** — on 429, consolidate — not IP tricks, not spam asks.
- **Red-team your ask** — would you accept this assistance if you were the operator?

### Architecture texture (same ethics)

- **Key custody** — `vault_only`, `donor_colocated`, `in_transit` on graph when keys move.
- **Blast-radius budgets** — max keys per donor; reject all-keys-one-VPS.
- **Warm spare** — operator-owned fallback beats assuming donors stay up.
- **Read-only donors** — mirror public datasets; food is bandwidth not secrets.
- **Internal newspaper** — optional weekly wins/limitations/next non-key ask for operator skim.
- **Letters to future-self** — *when email exists, run signup X* linking needs to executive plans.

### Discovery (still autonomous)

- **Scent trails** — follow official doc links monthly, not directory SEO.
- **Anti-catalog** — rejected services + why, to avoid re-probing.
- **Gap birthdays** — needs open >30d: escalate or deprioritize explicitly.
- **Cross-domain meals** — one key → many needs (email → signups → SMS); graph one→many.

## Capabilities beyond inference (search, grounding, APIs)

Think **out of the box**: the bottleneck is often not another LLM but **live data** (web search, instant answers, structured facts).

- Read [WEB_SEARCH_AND_TOOLS_OCT2026.md](WEB_SEARCH_AND_TOOLS_OCT2026.md) and `research tool-entitlements --class A`.
- **Brave** — SERP (`web/search`) vs **Answers** (instant grounded replies); Class B monthly credits; probe with `research probe-brave-search`.
- **SERP alternatives** — self-hosted OpenSERP on the body server; Wikipedia for citations; avoid assuming Google CSE for new projects.
- When you find a new search API, add a row to `free_tier_tool_entitlements.json` with official limits + conservative enforced caps — same discipline as LLM entitlements.
- Wire through **approved tools + sandbox**; vault keys only.

## Architecture patterns (consider — do not wait for operator)

See **[AGENT_ARCHITECTURE_IDEAS.md](AGENT_ARCHITECTURE_IDEAS.md)** — donor/key affinity, sharded egress, movable keys, donor churn; mTLS brain→worker→API. Evaluate, document, request approval; respect ToS.

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
