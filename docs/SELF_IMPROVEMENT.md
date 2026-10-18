# Self-Improvement Workflow

## What works today

PrivateMind runs a **trusted workflow state machine** for tasks titled `Self-improvement: repository workspace`. The executive does **not** rely on the model to self-report success; phases advance in code with checkpoints stored in memory (`improvement_run`).

### Lifecycle phases

`init → discover → investigate → implement → verify → submit → record → done`

| Phase | Behaviour |
|-------|-----------|
| **Discover** | `repo_read_file`, `repo_list_dir` (focused reads, redacted) |
| **Investigate** | `run_tests`, `record_limitation` with evidence |
| **Implement** | `repo_write_file` (non-sensitive paths only) |
| **Verify** | Re-run tests; failed tests → task **failed** (no success recorded) |
| **Submit** | `git_branch`, `git_commit`, optional `git_push` (SSH vault key) |
| **Record** | `improvement_outcome` written by trusted core |

Restart-safe: checkpoints (`clone_done`, `commit_done`, etc.) prevent repeating irreversible steps.

## Operator commands

```bash
# Offline demo using bundled fixture logic (copy your repo or use seed)
privatemind improve seed-workspace --workspace lab --from-path ./tests/fixtures/improve_repo
privatemind improve run-local --workspace lab --from-path ./tests/fixtures/improve_repo

# Production path (requires vault + agent-github)
privatemind improve clone --repo-ssh-url git@github.com:ORG/PrivateMind.git --workspace privatemind
privatemind improve start --repo-ssh-url git@github.com:ORG/PrivateMind.git --workspace privatemind --run
```

## Allowlisted tools

**Repository:** `repo_read_file`, `repo_list_dir`, `repo_search`, `repo_write_file`  
**Git (SSH):** `git_clone`, `git_branch`, `git_commit`, `git_push`, `git_diff`, `git_status`, `run_tests`  
**Memory:** `record_limitation` (trusted), `remember` (unverified tool output only)

## Human approval (enforced in code)

- Writes/commits touching **security-sensitive paths** (`src/privatemind/vault/`, `src/privatemind/security/`, etc.) are blocked; task moves to **blocked** with `request_human_help`.
- Model `complete_task` on self-improvement tasks is **rejected**.
- No auto-merge to `main`; push creates a remote branch only.

## Credentials

Vault secrets are redacted from audit logs and repo read output patterns. Tool `remember` cannot promote rows to trusted kinds (`system`, `improvement_outcome`, …).

## Reproduce the demonstrated cycle (tests)

```bash
pytest tests/test_self_improvement_loop.py -q
```

Uses fixture repo with intentional `calc.add` bug, full workflow, restart test, and failed-verify path.
