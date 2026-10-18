# Self-Improvement Workflow (Milestone 2)

## Objective

Inspect an authorized repository over **git+SSH**, track limitations with evidence, implement changes in an isolated workspace, run tests, and **push a branch** for human review (no auto-merge).

## Prerequisites

- Agent is **alive** (`privatemind wake`) with GitHub account **`agent-github`** in the vault
- Repository URL must be **`git@github.com:...`** (SSH only — no PAT/HTTP API for routine git)

## Operator commands

```bash
# Clone into ~/.privatemind/workspaces/<name>
privatemind improve clone \
  --repo-ssh-url git@github.com:YOUR_ORG/PrivateMind.git \
  --workspace privatemind

# Enqueue self-improvement executive task
privatemind improve start \
  --repo-ssh-url git@github.com:YOUR_ORG/PrivateMind.git \
  --workspace privatemind \
  --branch cursor/self-improve \
  --run
```

## Allowlisted git tools (executive)

| Tool | Purpose |
|------|---------|
| `git_clone` | Clone via SSH using vault key |
| `git_status` | Short status |
| `git_branch` | Create/checkout branch |
| `git_diff` | Working tree or staged diff |
| `git_commit` | Stage paths (optional) and commit |
| `git_push` | Push via SSH (`agent-github` default) |
| `run_tests` | Default `python3 -m pytest -q` in workspace |
| `record_limitation` | Persist structured limitation in memory |

All git network operations use **`GIT_SSH_COMMAND`** with the vault private key — same path as `privatemind wake` health checks.

## Safeguards

- Workspaces confined under `~/.privatemind/workspaces/`
- Repository file content is **untrusted**; policies live in trusted docs/config
- **Push does not merge** — human review on GitHub remains required
- Security-boundary changes require explicit human approval (future: blocked paths in commit tool)

## Evaluation

Record outcomes with `ImprovementTracker.record_outcome` (API) or memory kind `improvement_outcome` after tests pass/fail.
