# Contributor / donor — getting started

You are **giving capacity** to a PrivateMind network run by a human administrator — not joining a consumer app. Read this before submitting an intent on the portal.

---

## What you might offer

| Tier | You provide | Typical setup |
|------|-------------|---------------|
| **Bronze** | Compute only (VM, homelab) | Pair worker, mTLS; **no** API keys yet |
| **Silver** | Scoped **API keys** on **your** machine | Keys stay on your egress IP; one or few providers |
| **Gold** | Sustained compute + keys + attestation | Long-term; admin assigns contributor id |

You can **revoke** anytime: stop worker, rotate keys, ask admin to unpair.

---

## Safe expectations

- You are **not** root on the operator’s brain or vault.
- Do **not** send personal inbox passwords, mainnet wallets, or broad cloud root keys.
- The agent may document your donation in a graph; you can ask admin to remove your contributor row.

---

## Steps (happy path)

1. Open the operator’s **portal** URL (they may give you an SSH tunnel command first).
2. Read **donor instructions** on the portal.
3. Submit **donor intent** (name, contact, bronze/silver/gold, notes).
4. Wait for admin to contact you with **pairing** steps ([WORKER_PROTOCOL.md](WORKER_PROTOCOL.md), [REMOTE_WORKER.md](REMOTE_WORKER.md)).
5. Run `privatemind worker init` / `worker serve` on **your** machine when instructed.
6. Scope keys to providers you agreed — not “every API.”

Detailed playbooks are **written by the agent** over time: [DONOR_AND_HELPER_INSTRUCTIONS.md](DONOR_AND_HELPER_INSTRUCTIONS.md).

---

## Helpers without servers

Review PRs, reproduce bugs, edit docs — see portal **helper** page. Zero infrastructure required.
