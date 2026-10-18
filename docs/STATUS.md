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

WAN mTLS, multi-tenant leases, quarantine — not implemented.

## Not implemented

- Full adversarial worker pipeline (M4 generalisation beyond sha256)
- Resource leases and multi-contributor scheduling (M5+)
- Autonomous production promotion

## Next milestone

Implement **local worker process** against `worker/contract.py`: pairing, signed job/response envelopes, and verification hooks feeding existing `tool_trace` / `VerificationRecord` without exposing the vault or full memory DB.
