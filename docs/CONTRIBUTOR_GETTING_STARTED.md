# Contributor / donor — getting started

You are **giving capacity** to a PrivateMind network run by a human administrator — not joining a consumer app. Read this before submitting an intent on the portal.

**Resource menu (levels, CPU/GPU/storage, S3, Drive, etc.):** [DONOR_RESOURCE_TIERS.md](DONOR_RESOURCE_TIERS.md) — also on the portal as `/instructions/donor-resources` and JSON `/api/v1/donor/catalog`.

---

## How much you can offer (commitment level)

Pick the **smallest** level you are happy with — all are useful.

| Level | You give |
|-------|----------|
| **Traffic only** | Allowlisted HTTPS egress (API traffic relay); no shell |
| **Minor script** | Small sandboxed jobs (short CPU/RAM cap) |
| **Medium worker** | Paired worker for scheduled jobs; optional scoped API keys |
| **Full worker** | Long-lived worker; broader jobs — still **no** access to the operator’s vault or memory |

Legacy portal field **`offer`**: `bronze` / `silver` / `gold` still works — see catalog `legacy_offer_tiers`.

---

## What kind of resources

Check any that apply in your intent (`resource_kinds`):

- **Egress / bandwidth** — stable IP for API calls  
- **CPU time** — VM, homelab, always-free cloud  
- **GPU time** — batch inference or probes (not assumed 24/7 training)  
- **RAM / local disk** — cache for models or datasets on your machine  
- **Object storage** — S3-compatible bucket (yours or free-tier R2/B2)  
- **Sync folder** — Dropbox / OneDrive / Google Drive **scoped folder** (automation limits — admin reviews)

**Paid service donation:** If you pay for Wasabi, AWS, Dropbox Pro, etc. and want to **share scoped access**, set `paid_service_donation: true` in the intent — the operator provisions secrets via CLI vault, never in the portal POST.

---

## Storage (free-first network)

The project tries to live on **free / low-cost** services; **donated buckets** are welcome.

| Examples | Role |
|----------|------|
| **Cloudflare R2**, **Backblaze B2** | S3 API; good for artifacts (verify current free caps) |
| **Donated S3 bucket** | Best when you create IAM scoped to a prefix |
| **Google Drive / Dropbox / OneDrive** | Often **manual or low-rate** sync — not a silent data hose |
| **GitHub Releases / Actions artifacts** | Small public or CI outputs |

Full list with A/B/C classes: [`data/donor_resource_catalog.json`](data/donor_resource_catalog.json).

---

## Safe expectations

- You are **not** root on the operator’s brain or vault.
- Do **not** send personal inbox passwords, mainnet wallets, or cloud **root** keys.
- You can **revoke** anytime: stop worker, rotate keys, ask admin to unpair.

---

## Steps (happy path)

1. Open the operator’s **portal** URL.
2. Read **donor-resources** + this page.
3. `GET /api/v1/donor/catalog` if you build the JSON by script.
4. `POST /api/v1/donor/intent` with contact, `offer`, optional `commitment_level`, `resource_kinds`, `storage_backends`, notes.
5. Admin contacts you for **pairing** ([WORKER_PROTOCOL.md](WORKER_PROTOCOL.md)) and/or vault scoped storage creds.

Agent playbooks over time: [DONOR_AND_HELPER_INSTRUCTIONS.md](DONOR_AND_HELPER_INSTRUCTIONS.md).

---

## Helpers without servers

Review PRs, reproduce bugs, edit docs — portal **helper** page. Zero infrastructure.
