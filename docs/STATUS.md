# Implementation Status Report

## Demonstrated (Milestone 1 + onboarding)

| Capability | Evidence |
|------------|----------|
| README-first bootstrap | Operator flow: vault → accounts → setup-check → wake |
| Encrypted credential vault | PBKDF2 + Fernet; `tests/test_vault_and_wake.py` |
| Account types | LLM, GitHub SSH, SSH host via CLI |
| SSH/git CLI preference | Wake probes `ssh -T git@host` and optional `git ls-remote` |
| Wake / readiness | `privatemind wake`, `setup-check`, lifecycle memory |
| Git self-improvement (M2) | SSH git tools, workspaces, `improve clone/start`, tests |

## Demonstrated (Milestone 1 core)

| Capability | Evidence |
|------------|----------|
| Persistent task manager | SQLite `tasks` table, states, retries, decision log |
| Restart recovery | `test_restart_recovery_continues_pending_task` |
| Memory with provenance | `memory_entries` + trust labels |
| Capability registry | Seeded models/tools; CLI `capabilities` |
| Controlled tools | Allowlisted builtins only |
| Model abstraction | Heuristic + optional OpenAI-compatible backend |
| Human assistance | Pending queue, answer unblocks task |
| End-to-end demo | CLI `demo --run` computes hash, stores memory, completes task |

## Incomplete (by design for v0.1)

- Self-improvement / GitHub loop (M2)
- Worker pairing, encryption, leases (M3–M5)
- Adversarial result verification pipeline (M4)
- Multi-node scheduling and resource contribution (M5–M6)

## Next prioritized improvements

1. **M2:** Git read tool + limitation records + worktree dev + PR submission hook
2. **M3:** Ed25519 identity, pairing CLI, local worker process over TCP+mTLS
3. **M4:** Deterministic re-checks, schema validation, quarantine state machine
4. **Planner quality:** Structured action schema validation before tool invoke
5. **Operational:** Configurable budgets and approval policies for external spend

## Verification guarantees (honest)

v0.1 tests exercise persistence, tool allowlists, and human unblock paths. They do **not** prove security against a networked malicious worker or prompt injection against a remote LLM backend.
