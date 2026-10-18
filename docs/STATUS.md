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
- `gh pr create` not integrated — open PR manually on pushed branch.
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

## Next milestone

Operational hardening: dynamic tool loading after approval, `gh pr create` integration, production PKI.
