# Credential vault

PrivateMind keeps API keys and SSH private keys in an **encrypted vault** on disk (`credentials.vault`). This is the agent's internal account manager; it is separate from the memory database and is only writable through trusted CLI paths.

## Design rules

- Secrets are encrypted at rest with **PBKDF2 + Fernet** (`cryptography`).
- Unlock with `PRIVATE_MIND_VAULT_PASSPHRASE` (recommended for non-interactive runs) or `--passphrase` on CLI commands.
- `privatemind account list` shows **metadata only** (account names, hosts, secret field names — never values).
- SSH keys materialize under `~/.privatemind/runtime/ssh/` with mode `0600` only when running git/ssh probes or future CLI tools.
- Prefer **git over SSH** and **ssh** for servers — not GitHub HTTPS tokens — to reduce bot-detection friction and keep keys scoped.

## Account kinds

| Kind | Purpose | Public fields | Secret fields |
|------|---------|---------------|---------------|
| `llm` | Inference API | `base_url`, `model` | `api_key` |
| `github` | Dedicated GitHub user | `host`, `transport=ssh`, optional `probe_repo_ssh_url` | `private_key` |
| `ssh_host` | Test/production server | `host`, `user`, `port` | `private_key` |

## Readiness

The agent is **alive** when the vault is unlocked and at least one enabled `llm` and one enabled `github` account exist. Optional `ssh_host` accounts are probed during `privatemind wake`.

## Threat notes

- Anyone with the vault passphrase and filesystem access can decrypt secrets — protect the data directory permissions.
- Runtime key files are a exposure surface while present; they are intended for local CLI use only.
- Workers (future) must **not** receive the vault or bulk secret export.
