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

## Status

Not implemented in v0.1; central agent runs locally. This document stabilizes the intended interface before coding M3.
