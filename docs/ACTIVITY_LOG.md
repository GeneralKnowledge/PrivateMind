# Activity log

See **what the system is up to** — wakes, ticks, tools, workers, mode changes, donor intents. Stored in SQLite (`audit_events`); secrets redacted on write.

**Future:** the executive should review the log on wake and summarize for the operator when useful ([AGENT_RUNTIME_CONTROL.md](AGENT_RUNTIME_CONTROL.md)).

---

## Commands

```bash
privatemind log                  # last 40 events, newest first
privatemind log --limit 100
privatemind log --category wake
privatemind log --json
privatemind log --categories     # distinct category names
privatemind log --follow         # poll every 3s (Ctrl+C to stop)
```

Example line:

```
2026-10-18T18:00:00+00:00  executive_step          task_id=… state=running completed=false
```

---

## Categories (typical)

| Category | Meaning |
|----------|---------|
| `system_init` | `privatemind init` |
| `wake` | Wake activated or blocked |
| `operational_mode` | slow_start / test / production |
| `executive_tick` | CLI `tick` batch |
| `executive_step` | One task step |
| `model_request` / `model_response` | LLM call (no prompt body) |
| `tool_result` | Approved tool finished |
| `worker_delegate_failed` / worker success | Worker hub |
| `donor_intent` | Portal submission |
| `github_ssh_probe` | Wake health |

---

## Operator tips

- After setup: `privatemind log --category wake`
- While debugging: `privatemind log --follow`
- Agent: parse `privatemind log --json` — do not log vault material elsewhere.
