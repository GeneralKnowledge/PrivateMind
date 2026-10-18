# Threat Model (initial)

## Scope

This document covers v0.1 (local trusted core) and stated assumptions for upcoming worker and self-improvement features.

## Assets to protect

1. **Private runtime state** — SQLite database under `~/.privatemind` (tasks, memory, audit).
2. **Credentials** — API keys and SSH private keys in encrypted `credentials.vault`; env vars are legacy fallback only.
3. **Executive integrity** — task states, retry policy, human-gating decisions.
4. **Trust policies** — tool allowlists, future worker authorization (not yet enforced over network).

## Adversaries

| Adversary | Example | v0.1 mitigations | Gaps |
|-----------|---------|------------------|------|
| Malicious prompt injection via task text | Hidden instructions in description | System prompt + core parses actions; no direct exec | Model may choose bad actions if LLM backend used without review |
| Malicious worker | Signed but false compute result | `tests/test_worker_adversarial.py` | M4 verification + auto-quarantine |
| Malicious contributor (future) | Sybil workers | N/A yet | Leases, reputation-informed checks |
| Compromised tool output | Forged JSON | Tools run in-process with fixed API | No sandbox yet for arbitrary code |
| Malicious repo content (future) | Issue/PR injection | N/A yet | M2 read-only + policy |
| Malicious self-update (future) | PR weakening verification | N/A yet | Protected branches, human merge |

## Guarantees (v0.1)

- **Persistence:** Task progress survives process restart (integration tests).
- **Tool confinement:** Only allowlisted tools; unknown tools rejected.
- **Memory provenance:** Structured labels on stored knowledge.
- **Human gate:** Assistance requests block tasks until answered.

## Enforced mechanisms (self-improvement)

- `remember` tool writes **unverified** memory; trusted kinds blocked.
- Security-sensitive repo paths blocked for `repo_write_file` / `git_commit`.
- Self-improvement success requires workflow `verify_passed` — not model `complete_task`.
- Audit entries redact common secret patterns.

## Non-goals (still)

- Encrypted worker transport
- Remote attestation
- Proof of correct ML inference
- Automatic merge to production

## Security assumptions

- The host running the trusted core is not fully compromised.
- Operators protect `PRIVATE_MIND_*` secrets and the data directory permissions.
- Human reviewers remain in the loop for privileged codebase changes until automated promotion is justified.
