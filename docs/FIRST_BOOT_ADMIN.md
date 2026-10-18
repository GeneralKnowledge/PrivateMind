# First boot — primary administrator

You are the **first human** on the network: trust floor owner, vault passphrase holder, and merge authority on `main`. The agent will grow topology and write donor playbooks; **you** complete this checklist once per brain install.

Estimated time: one focused session (LLM + GitHub accounts ready).

---

## Before you start

| Prepare | Why |
|---------|-----|
| Dedicated **LLM API key** | Agent cannot wake without inference |
| Dedicated **GitHub user** + SSH key | Git/self-improvement over SSH only |
| A machine for the **brain** (VM or laptop) | Persistent `~/.privatemind` |
| Strong **vault passphrase** | Store in a password manager; use `PRIVATE_MIND_VAULT_PASSPHRASE` for non-interactive runs |

Optional now, later via assistance: agent email, SMS, search API, second worker VM.

---

## Boot sequence (order matters)

### 1. Install and init data dir

**One-liner (read [scripts/install.sh](../scripts/install.sh) before piping):**

```bash
curl -fsSL https://raw.githubusercontent.com/GeneralKnowledge/PrivateMind/main/scripts/install.sh | bash
```

**Or from a clone:**

```bash
git clone https://github.com/GeneralKnowledge/PrivateMind.git
cd PrivateMind
./scripts/install.sh
privatemind mode status    # expect slow_start after init
```

Stay on **`slow_start`** until you are comfortable; use **`test`** when pairing a **new worker**. See [OPERATIONAL_MODES.md](OPERATIONAL_MODES.md).

### 2. Vault (you alone)

```bash
export PRIVATE_MIND_VAULT_PASSPHRASE='…'
privatemind vault init --passphrase "$PRIVATE_MIND_VAULT_PASSPHRASE"
privatemind vault status
```

Never commit the passphrase. Back up `~/.privatemind/vault.enc` with the same care as a password database export.

### 3. Core node identity (for workers later)

```bash
privatemind node init
```

Save the printed **fingerprint**. You will pair workers and export trust bundles for remote VMs.

### 4. Register minimum accounts

```bash
privatemind account add-llm --name primary …
privatemind account add-github --name agent-github …
privatemind account list
```

See [README.md](../README.md) §3 for full flags.

### 5. Readiness

```bash
privatemind setup-check
```

Target `"level": "alive"` with vault unlocked.

### 6. First wake

Prefer small steps while in `slow_start`:

```bash
privatemind wake
privatemind tick --steps 1
privatemind status    # includes operational_mode
# later: privatemind wake --run
privatemind mode set production   # when ready for normal throughput
```

Confirm post-wake bootstrap task ran. Skim assistance queue — expect **batched** asks over time, not spam every minute.

### 7. Portal (for future donors — optional on day one)

On the brain host, start the local **resource portal** (instructions + intent skeleton):

```bash
privatemind portal serve
# Open http://127.0.0.1:8780 — use SSH tunnel or reverse proxy when exposing beyond localhost
```

See [PORTAL.md](PORTAL.md). Day one you can skip this until you want contributors.

### 8. Mark yourself admin (local note)

```bash
privatemind portal admin-note --text "Primary admin: <your name>, created $(date -I)"
```

Stored under the data dir for the agent and your audit — not sent anywhere.

### 9. Clone repo for self-improvement

```bash
privatemind improve clone --repo-ssh-url git@github.com:YOUR_ORG/PrivateMind.git --workspace privatemind
```

---

## Your ongoing job (not the agent’s)

| You always | Agent may |
|------------|-----------|
| Hold vault passphrase | Request scoped keys via assistance |
| Merge to `main` | Open draft PRs on branches |
| Approve `tool-request` / sandbox runners | Propose tools |
| Pair/revoke workers; register contributors | Draft donor playbooks |
| Run `portal serve` (or systemd) when accepting donors | Read donor intents you approve |

**Non-key help counts:** review PRs, DNS, feedback, repro bugs — see agent’s `solo-operator` playbook when it exists.

---

## Solo phase defaults

- One operator is a **valid** topology — not “waiting for community.”
- Prefer portal **localhost** until mTLS worker PKI and firewall rules are ready.
- Read [GRADUATED_AUTONOMY.md](GRADUATED_AUTONOMY.md) and [THREAT_MODEL.md](THREAT_MODEL.md) once; you set the floor, the agent optimizes above it.

---

## When something fails

| Symptom | Check |
|---------|--------|
| `setup-check` not alive | LLM + GitHub accounts enabled, vault unlocked |
| GitHub probe fails | Dedicated user, key in vault, `ssh -T git@github.com` manually |
| Wake loops on assistance | Normal early on — batch responses; see [AGENT_MIND_LAYERS.md](AGENT_MIND_LAYERS.md) food vs life |
| Donor cannot connect | Worker not paired; see [REMOTE_WORKER.md](REMOTE_WORKER.md) |

---

## Related

- [README.md](../README.md) — install reference
- [PORTAL.md](PORTAL.md) — donor/helper HTTP entry
- [DONOR_AND_HELPER_INSTRUCTIONS.md](DONOR_AND_HELPER_INSTRUCTIONS.md) — agent-authored playbooks (empty until agent writes them)
- [DEDICATED_SERVER.md](DEDICATED_SERVER.md) — brain + body on one host
