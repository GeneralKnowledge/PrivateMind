# Worker Communication Protocol (draft — Milestones 3–5)

Application-level messages (transport-independent). Transport target: mutual TLS or Noise-based session after explicit pairing.

## Identity

Each node generates an Ed25519 key pair; public keys fingerprinted for pairing approval by the operator.

## Message envelope (v0 draft)

```json
{
  "v": 1,
  "msg_id": "uuid",
  "sent_at": "RFC3339",
  "sender_id": "node fingerprint",
  "recipient_id": "node fingerprint",
  "payload_type": "job_offer | job_result | capability_ad | revoke",
  "payload": {},
  "signature": "base64"
}
```

Freshness: monotonic counters or short TTL; replay cache on receiver.

## Resource lease (draft)

```json
{
  "lease_id": "uuid",
  "worker_id": "fingerprint",
  "capabilities": ["compute_sha256"],
  "operations_allowed": ["compute_sha256"],
  "limits": {"max_jobs_per_hour": 100},
  "expires_at": "RFC3339",
  "revoked": false
}
```

Workers receive **job packages** containing only the minimum input; never the full memory database or executive policies.

## Result provenance (M4)

Job results include input hash, output, execution metadata, and signature. The trusted core records verification outcome separately from acceptance.

## Code alignment (pre-network)

Python datatypes in `src/privatemind/worker/contract.py` mirror this envelope:

- `JobPackage` — scoped payload + `input_hash` (worker sees only the job body).
- `JobResponseEnvelope` — signed response linked to `job_id`.
- `VerificationRecord` — separates **authenticity** from **correctness** and **acceptance** (matches trusted-core decision flow used for self-improvement test results).

Executive memory already stores tool/worker output as `tool_output` / `unverified` until the trusted core promotes or rejects.

## Status (M3 — local TCP prototype)

Implemented on **localhost**:

| Feature | Status |
|---------|--------|
| Ed25519 node identities | `privatemind node init`, `privatemind worker init` |
| Operator pairing | `privatemind worker pair` |
| Scoped leases | `privatemind worker lease` |
| Signed envelopes v1 | `worker/envelope.py` |
| Replay cache | `worker_replay` table |
| TCP job offer / result | `privatemind worker serve` on `127.0.0.1:8765` |
| Correctness check | `compute_sha256` recomputed in core (authentic but false → rejected) |

**Remote mTLS (lab PKI):** `privatemind worker pki-init`, pair with `--host`/`--mtls`, `worker serve --host 0.0.0.0 --mtls`. See [REMOTE_WORKER.md](REMOTE_WORKER.md).

**M4 adversarial verification (implemented):**

| Feature | Status |
|---------|--------|
| Response schema validation | `worker/verifier.py` |
| `input_hash` binding on results | rejected if mismatch |
| Trust states | `paired`, `restricted`, `quarantined`, `revoked` |
| Auto-quarantine | after `PRIVATE_MIND_WORKER_QUARANTINE_FAILURE_THRESHOLD` consecutive failures (default 3) |
| Operator CLI | `privatemind worker trust quarantine|release|restrict|restore|revoke` |

`restricted` workers may receive jobs; the core verifies correctness but never **accepts** results until restored to `paired`.

Not yet: production CA integration, worker advertisements, Sybil resistance at scale, general proof systems.

### Quick demo

```bash
privatemind node init
privatemind worker init
privatemind worker pair <worker-fp> --public-key-b64 <worker-pub>
privatemind worker lease <worker-fp> --operation compute_sha256
# terminal A:
privatemind worker serve
# terminal B:
privatemind worker demo --text hello
```
