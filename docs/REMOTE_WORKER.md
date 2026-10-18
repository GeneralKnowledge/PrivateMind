# Remote worker on a second VM (mTLS)

Run the **brain** on your main server and a **worker** on a test VM. Transport uses **mutual TLS** plus the existing **Ed25519 signed job envelopes** (defence in depth).

## Brain server (trusted core)

```bash
privatemind init
privatemind node init
privatemind worker pki init --san 203.0.113.10 --san worker.test   # worker VM IP/DNS in cert SAN
privatemind node export-trust --output /tmp/trusted_core.json

# After worker generates its Ed25519 identity on the VM:
privatemind worker pair <worker-ed25519-fp> \
  --public-key-b64 <worker-ed25519-pub> \
  --host 203.0.113.10 \
  --port 8765 \
  --mtls \
  --label test-vm

privatemind worker lease <worker-ed25519-fp> --operation compute_sha256
privatemind worker demo --text remote-hello
```

Core PKI material stays on the brain: `~/.privatemind/mtls/{ca.crt,core-client.crt,core-client.key}`.

## Worker VM (minimal footprint)

Copy to the VM (scp/rsync):

| File | Purpose |
|------|---------|
| `worker_identity.json` | Worker Ed25519 identity (from `privatemind worker init` on VM) |
| `trusted_core.json` | Core Ed25519 **public** key only (`node export-trust`) |
| `mtls/ca.crt` | Trust anchor |
| `mtls/worker-server.crt` | Server cert |
| `mtls/worker-server.key` | Server private key |

On the VM (same `PRIVATE_MIND_DATA_DIR` layout):

```bash
export PRIVATE_MIND_DATA_DIR=/var/lib/privatemind-worker
privatemind worker serve --host 0.0.0.0 --port 8765 --mtls
```

Open **only** port 8765 from the brain IP in the VM firewall.

## Security notes

- mTLS authenticates **transport peers** (core client cert ↔ worker server cert). Job **correctness** still requires Ed25519 envelopes + local verification (e.g. sha256 re-check).
- Do **not** copy `core_identity.json` (private key) to the worker VM — use `trusted_core.json` only.
- Dev PKI from `worker pki init` is for lab use; replace with your org CA for production.

## Environment

| Variable | Brain | Worker VM |
|----------|-------|-----------|
| `PRIVATE_MIND_DATA_DIR` | `~/.privatemind` | e.g. `/var/lib/privatemind-worker` |
| `PRIVATE_MIND_WORKER_HOST` | default target if peer has no endpoint | — |
| `PRIVATE_MIND_WORKER_USE_MTLS` | `1` (default when PKI present) | enable `--mtls` on serve |
