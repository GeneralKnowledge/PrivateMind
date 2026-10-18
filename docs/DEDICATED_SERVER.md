# Dedicated-server deployment

Many operators run PrivateMind on a **single server that hosts both the trusted core (“brain”) and the tools it uses (“body”)**. That layout matches how you described your plan: give the agent the tools it needs, on the machine where its persistent state already lives.

## Why co-location helps

When the executive, memory, vault, and workspaces live on the same host as most tools:

- **Continuity** — Destroying the environment destroys the agent’s checkpointed work, limitation history, and vault-backed identities. A persistent agent that optimises for long-running goals has a practical incentive not to brick its only home.
- **Latency** — Git, tests, and repo tools run locally without shipping the private database elsewhere.
- **Control** — You still choose which tools exist; the agent proposes, you (or policy) grant.

Co-location is **not** a security proof. A compromised planner, malicious repo content, or a bad tool implementation can still cause harm on that host. It mainly aligns **incentives** and **operations**.

## Giving “any tool it asks for”

Recommended pattern on your server:

1. Agent calls **`request_tool`** (justification, purpose, risk notes) — queued for you.
2. You implement or wire the tool (script, CLI wrapper, MCP adapter) on **that server only**.
3. You **`tool-request approve --runner-arg ...`** — registers the capability and runs it in a **sandboxed subprocess** (scrubbed env, isolated cwd, CPU/memory limits). On the body server you can install **bubblewrap** (`bwrap`) and prepend it to `runner_argv` for stronger FS/network isolation when `unshare` is unavailable.
4. Optional: set `PRIVATE_MIND_AUTO_APPROVE_TOOL_REQUESTS=1` only on an isolated lab box if you truly want zero-friction experiments (not recommended for production).

After the trust floor is stable, the agent may prioritize its own hardening using [IDEAS_FOR_THE_AGENT.md](IDEAS_FOR_THE_AGENT.md) — suggestions, not orders. See [GRADUATED_AUTONOMY.md](GRADUATED_AUTONOMY.md).

The agent must **not** silently add tools by editing its own registry or trusting model output. Expansion goes through the queue so you keep a paper trail.

## What stays protected even on a dedicated server

| Asset | Why it stays gated |
|-------|---------------------|
| Vault passphrase / raw keys | Never in prompts, memory facts, or audit |
| `improvement_outcome`, `system` memory kinds | Trusted-core promotion only |
| Security-sensitive repo paths | Still require human review before commit |
| Production git default branch | No auto-merge; push feature branches only |

## Workers later

When you add remote workers, they still must **not** receive the full vault or memory DB. The dedicated server remains the trust boundary; workers get scoped jobs only.

## Related commands

```bash
privatemind tool-request list
privatemind tool-request approve <id> --capability-id tool.custom.mything
```

See [CREDENTIALS.md](CREDENTIALS.md) and [THREAT_MODEL.md](THREAT_MODEL.md).
