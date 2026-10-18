# Implementation Status (authoritative with tests)

## Demonstrated end-to-end

| Area | Evidence |
|------|----------|
| Persistent executive + recovery | `tests/test_milestone1.py` |
| Vault + wake | `tests/test_vault_and_wake.py` |
| Git SSH tools (mocked) | `tests/test_git_tools.py` |
| **Self-improvement cycle** | `tests/test_self_improvement_loop.py` — discover → fix → test → commit → record |
| **Restart mid-cycle** | `test_self_improvement_survives_restart` |
| **Failed tests → failed outcome** | `test_failed_tests_block_success` |
| **Security boundaries** | `tests/test_security_boundaries.py` — redaction, sensitive paths, tool allowlist |

## Self-improvement (current behaviour)

- Trusted workflow driver for `Self-improvement:*` tasks (not LLM self-judgment).
- Reads docs/source via scoped repo tools; does not dump full tree into prompts by default.
- Records limitations with evidence; stores tool traces as **unverified**.
- Pushes development branches via SSH when configured; **does not merge to main**.

## Partial / operator-dependent

- Live `git push` to GitHub requires real `agent-github` vault key and remote.
- Draft `gh pr create` runs when `gh` is on PATH; merge to `main` remains manual.
- LLM planner optional for non-workflow tasks; heuristic demo still Milestone 1 only.

## Worker network (M3 — local)

| Feature | Evidence |
|---------|----------|
| Ed25519 identities + pairing | `tests/test_worker_network.py` |
| Signed job/response | `worker/hub.py`, `worker/service.py` |
| Replay protection | `worker/pairing_store.py` |
| False signed result rejected | `test_false_signed_result_rejected` |

Remote mTLS: `tests/test_worker_mtls.py`.

## Worker adversarial verification (M4)

| Feature | Evidence |
|---------|----------|
| Schema + input_hash checks | `tests/test_worker_adversarial.py` |
| Trust states (restricted / quarantined / revoked) | `worker/trust.py`, `worker pair trust *` CLI |
| Auto-quarantine on consecutive failures | `test_auto_quarantine_after_failures` |
| Restricted: verify but do not accept | `test_restricted_worker_never_auto_accepts` |

## Worker scheduling and leases (M5)

| Feature | Evidence |
|---------|----------|
| Lease expiry + max job budget | `tests/test_worker_scheduling.py` |
| Round-robin scheduler | `test_scheduler_round_robin` |
| Contributor onboarding + scoped schedule | `worker contributor *`, `test_contributor_scoped_schedule` |

## Not implemented

- General proof systems beyond operation-specific recomputation (e.g. arbitrary compute)
- Autonomous production promotion
- Production-grade multi-tenant isolation beyond contributor scoping

## Operational hardening (post-M5)

| Feature | Evidence |
|---------|----------|
| Protected-path manifest (writes/commits) | `security/protected_manifest.py`, `test_protected_path_blocks_write` |
| Draft PR via `gh` after self-improvement push | `integrations/gh_cli.py`, workflow submit phase |
| Approved tool **sandboxed** runner | `tools/sandbox.py`, `approved_runner.py`, env scrub + rlimits + isolated cwd |
| Memory trust promotion CLI | `memory promote`, `test_memory_promotion_transitions` |
| Worker health in setup-check / status | `activation/worker_health.py` |
| Reputation-aware scheduling sort | `pairing_store.worker_reputation` |
| Pluggable worker verifiers | `worker/verifier_registry.py` |
| Assistance webhook | `PRIVATE_MIND_ASSISTANCE_WEBHOOK_URL` |

## Tool sandbox (approved tools)

| Feature | Evidence |
|---------|----------|
| Scrubbed env (no vault tokens in child) | `test_sandbox_env_not_visible_to_runner` |
| Isolated cwd under `runtime/tool_sandbox/` | `test_sandboxed_runner_uses_isolated_cwd` |
| CPU / memory / fd rlimits | `tools/sandbox.py`, `test_memory_limit_can_stop_runaway` |
| Optional network namespace | `unshare -n` when permitted on host; else document bubblewrap on body server |

Configure defaults: `PRIVATE_MIND_TOOL_SANDBOX_*`. Per-tool overrides via `tool-request approve --sandbox-memory-mb`, `--sandbox-network`.

## Agent-directed improvements

Optional ideas live in [IDEAS_FOR_THE_AGENT.md](IDEAS_FOR_THE_AGENT.md). Provisional free-tier service research: [FREE_TIER_RESEARCH.md](FREE_TIER_RESEARCH.md), October catalogue [FREE_TIER_CATALOG_OCT2026.md](FREE_TIER_CATALOG_OCT2026.md) + [data/free_tier_entitlements.json](data/free_tier_entitlements.json), backlog [FREE_TIER_CANDIDATES.md](FREE_TIER_CANDIDATES.md), router metadata [data/free_tier_provider_catalog.json](data/free_tier_provider_catalog.json), CLI `privatemind portal serve|intents list|…` and `privatemind research donor-resources|capability-domains|capability-gaps|self-model|helper-playbooks|discover|…`. Donor tiers/storage: [DONOR_RESOURCE_TIERS.md](DONOR_RESOURCE_TIERS.md). Human onboarding: [FIRST_BOOT_ADMIN.md](FIRST_BOOT_ADMIN.md), [PORTAL.md](PORTAL.md). Agent mandate: [AGENT_CAPABILITY_MANDATE.md](AGENT_CAPABILITY_MANDATE.md). Mind layers: [AGENT_MIND_LAYERS.md](AGENT_MIND_LAYERS.md). Donor/helper (agent-authored): [DONOR_AND_HELPER_INSTRUCTIONS.md](DONOR_AND_HELPER_INSTRUCTIONS.md). Web search: [WEB_SEARCH_AND_TOOLS_OCT2026.md](WEB_SEARCH_AND_TOOLS_OCT2026.md). Philosophy: [GRADUATED_AUTONOMY.md](GRADUATED_AUTONOMY.md).

## Next steps (for the agent or operator — not a central roadmap)

- Harden sandbox on dedicated server (bubblewrap, dedicated UID, Landlock) — see IDEAS doc
- Production PKI rotation / cert expiry monitoring
- Sybil-resistant contributor policies beyond reputation sorting
- Human merge to `main` remains the promotion gate
- Additional worker verifiers for new job types
