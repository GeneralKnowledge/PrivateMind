# Self-Improvement Workflow (planned — Milestone 2)

## Objective

Enable the agent to inspect an authorized repository, track limitations with evidence, implement fixes in an isolated workspace, run tests, and open a pull request for human review.

## v0.1 foundation already in place

- Persistent limitation-friendly memory (`kind=limitation` convention documented here)
- Audit log for security-relevant events
- Executive suitable for long-running improvement tasks
- Capability registry extensible for `tool.git` operations

## Workflow (target M2)

1. **Discover** — Read architecture docs, issues, test output; add/update limitation records with severity and evidence.
2. **Propose** — Structured improvement proposal stored in memory and optionally as a GitHub issue draft.
3. **Implement** — Branch in isolated worktree; minimum permissions.
4. **Verify** — Run pytest/linters; capture baseline vs outcome metrics.
5. **Submit** — Open PR; never auto-merge security-sensitive changes.
6. **Evaluate** — Record success/failure; revert on regression.

## Safeguards

- Repository content is **untrusted data**; policies live in trusted config/docs.
- Changes affecting verification, auditing, or approval requirements require human review.
- The agent cannot approve its own privilege expansion.

## Next implementation tasks

- `ImprovementTracker` memory helpers and CLI
- Scoped GitHub/git tool with read-only default
- Sample end-to-end improvement task in integration tests
