# PrivateMind

**Start here.** PrivateMind begins as this README: you install the software, create a dedicated encrypted vault, register the accounts you want the agent to use, then **wake** it. Until accounts are configured, the core stays dormant — no pretending to be alive without keys.

The trusted core keeps private state, tasks, and memory. API keys and SSH identities live in an internal **credential vault**, not in chat logs or the memory database.

### Who you are (pick a path)

| Role | Start here |
|------|------------|
| **Primary admin (first boot)** | [docs/FIRST_BOOT_ADMIN.md](docs/FIRST_BOOT_ADMIN.md) — vault, node identity, wake, portal |
| **Contributor / donor** | Operator gives you a portal URL → [docs/CONTRIBUTOR_GETTING_STARTED.md](docs/CONTRIBUTOR_GETTING_STARTED.md) |
| **Helper (no servers)** | [docs/HELPER_GETTING_STARTED.md](docs/HELPER_GETTING_STARTED.md) |

**Local portal** (instructions + donor intent queue, no auto-provisioning):

```bash
privatemind portal serve   # http://127.0.0.1:8780
```

Details: [docs/PORTAL.md](docs/PORTAL.md).

**Slow start / test / production:** `privatemind init` sets **`slow_start`** throttles (ticks, probes, idle loops). [docs/OPERATIONAL_MODES.md](docs/OPERATIONAL_MODES.md) — use **`test`** for new workers.

---

## 0. What you are setting up

Prepare **separate accounts** for the agent (recommended):

| Account | Purpose |
|---------|---------|
| **LLM API** | Inference (OpenAI-compatible URL + key) |
| **GitHub user** | Dedicated user with SSH deploy key / SSH key — **git CLI over SSH only** (no PAT in HTTP URLs) |
| **Test server** | SSH host for experiments (optional but supported) |

The agent is instructed to **ask for more** over time — dedicated **email**, **SMS/phone**, **crypto wallet**, and eventually **fiat** within caps ([docs/AGENT_CAPABILITY_MANDATE.md](docs/AGENT_CAPABILITY_MANDATE.md)). You provision; it discovers and requests via assistance tasks — it does not open bank accounts or use your personal inbox.

Give the agent only what it needs. Revoke by disabling or deleting an account in the vault.

**Building without paid services:** Start with the October 2026 catalogue [docs/FREE_TIER_CATALOG_OCT2026.md](docs/FREE_TIER_CATALOG_OCT2026.md) and machine-readable [docs/data/free_tier_entitlements.json](docs/data/free_tier_entitlements.json) (Categories A/B/C, official vs enforced limits). Broader notes: [docs/FREE_TIER_RESEARCH.md](docs/FREE_TIER_RESEARCH.md). CLI: `privatemind research entitlements --class A`, `probe-api`, `github-sync` (discovery only).

---

## 1. Install

Requirements: Python 3.11+, `git`, and `ssh` on your PATH.

```bash
git clone https://github.com/GeneralKnowledge/PrivateMind.git
cd PrivateMind
python3 -m pip install -e ".[dev]"
privatemind init
```

Data directory (default): `~/.privatemind/`

---

## 2. Create the credential vault

Choose a strong passphrase. Non-interactive runs use the environment variable (do not commit this):

```bash
export PRIVATE_MIND_VAULT_PASSPHRASE='your-long-passphrase'
privatemind vault init --passphrase "$PRIVATE_MIND_VAULT_PASSPHRASE"
privatemind vault status
```

Details: [docs/CREDENTIALS.md](docs/CREDENTIALS.md)

---

## 3. Register accounts

### LLM (required to wake)

```bash
privatemind account add-llm \
  --name primary \
  --base-url https://api.openai.com/v1 \
  --model gpt-4o-mini \
  --api-key "$YOUR_API_KEY"
```

### GitHub over SSH (required to wake)

Create a **dedicated GitHub account** for the agent. Add an SSH public key, then store the **private** key in the vault:

```bash
privatemind account add-github \
  --name agent-github \
  --private-key-file ~/.ssh/agent_github_ed25519 \
  --probe-repo-ssh-url git@github.com:YOUR_ORG/PrivateMind.git
```

Policy: **always prefer `git` and `ssh` CLI** for GitHub (clone, fetch, push, ls-remote). Avoid GitHub HTTP APIs and personal access tokens for routine work — they trigger automation friction and broaden credential scope.

### Test server over SSH (optional)

```bash
privatemind account add-ssh-host \
  --name test-server \
  --host 203.0.113.10 \
  --user agent \
  --private-key-file ~/.ssh/agent_testserver_ed25519
```

List configured accounts (no secret values shown):

```bash
privatemind account list
```

---

## 4. Check readiness

```bash
privatemind setup-check
```

You want `"level": "alive"` — vault unlocked, at least one LLM account and one GitHub SSH account enabled.

---

## 5. Wake the agent

```bash
privatemind wake
```

This will:

1. Confirm readiness  
2. Record primary account names in trusted memory  
3. Probe `ssh -T git@github.com` (and optional `git ls-remote`) using the vault key  
4. Optionally probe SSH hosts  
5. Enqueue a short **post-wake bootstrap** task  

Run the executive after wake:

```bash
privatemind wake --run
privatemind status
```

---

## 6. Self-improvement (git + SSH only)

After wake, use the agent GitHub identity for all repository work (no PAT HTTP API):

```bash
privatemind improve clone \
  --repo-ssh-url git@github.com:YOUR_ORG/PrivateMind.git \
  --workspace privatemind

privatemind improve start \
  --repo-ssh-url git@github.com:YOUR_ORG/PrivateMind.git \
  --workspace privatemind \
  --branch cursor/self-improve
```

Executive tools: `git_clone`, `git_branch`, `git_commit`, `git_push`, `run_tests`, `record_limitation`, plus focused `repo_read_file` / `repo_write_file`. Self-improvement tasks run a **trusted workflow** (phases + checkpoints) — see [docs/SELF_IMPROVEMENT.md](docs/SELF_IMPROVEMENT.md).

Offline demonstration:

```bash
privatemind improve run-local --workspace lab --from-path tests/fixtures/improve_repo
pytest tests/test_self_improvement_loop.py -q
```

---

## 7. Day-two operations

| Command | Purpose |
|---------|---------|
| `privatemind tick --steps N` | Advance tasks |
| `privatemind task "..."` | Enqueue work |
| `privatemind status` | Tasks, checkpoint, human help queue |
| `privatemind portal serve` | Local web hub for donor/helper instructions + intents |
| `privatemind portal intents list` | Review submitted donor intents |
| `privatemind demo --run` | Offline milestone demo (no vault required) |
| `privatemind capabilities` | Registered models/tools |

Legacy env vars (`PRIVATE_MIND_LLM_*`) still work if no LLM vault account is present; **vault accounts take precedence** when unlocked.

---

## Worker network (M3 — local)

Pair a **second process** (or another machine later) without giving it your vault or memory DB:

```bash
privatemind node init
privatemind worker init
privatemind worker pair <worker-fingerprint> --public-key-b64 <...>
privatemind worker lease <worker-fingerprint> --operation compute_sha256
privatemind worker serve    # terminal A
privatemind worker demo     # terminal B
```

See [docs/WORKER_PROTOCOL.md](docs/WORKER_PROTOCOL.md). **Remote VM:** [docs/REMOTE_WORKER.md](docs/REMOTE_WORKER.md).

---

## Dedicated server (brain + body on one host)

If you run PrivateMind on its **own server** and plan to **grant tools as it asks**, use the request queue (do not paste credentials into chat):

```bash
# Agent uses request_tool → you approve on the same machine
privatemind tool-request list
privatemind tool-request approve <request-id>
```

Lab-only friction removal: `PRIVATE_MIND_AUTO_APPROVE_TOOL_REQUESTS=1` (registers capabilities automatically; you still wire execution). See [docs/DEDICATED_SERVER.md](docs/DEDICATED_SERVER.md).

---

## Architecture & security

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — trusted core vs future workers  
- [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) — adversaries and guarantees  
- [docs/SELF_IMPROVEMENT.md](docs/SELF_IMPROVEMENT.md) — repo/PR loop (next milestone)  
- [docs/STATUS.md](docs/STATUS.md) — what is demonstrated today  

---

## Development

```bash
pytest
```

---

## Roadmap (short)

1. Persistent core — **done**  
2. Self-improvement via **git/ssh** on the agent GitHub account — **next**  
3. Secure worker network  
4. Adversarial result verification  
5. Contributed resources with revocable leases  

---

## License

MIT — see [LICENSE](LICENSE).
