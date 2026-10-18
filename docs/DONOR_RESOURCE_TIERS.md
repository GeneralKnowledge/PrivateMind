# Donor resource tiers and storage (for humans + agent)

**Audience:** Contributors, primary admin, and the **executive** (routing graph). PrivateMind aims to live on **free / low-cost** infrastructure; **donated paid access** (S3 bucket, Pro Dropbox, etc.) is welcome when someone explicitly offers it.

Machine-readable menu: [`data/donor_resource_catalog.json`](data/donor_resource_catalog.json). Portal intents can reference these ids.

---

## Commitment level (how much of a machine)

Smallest useful donations matter. Pick the **highest level you are comfortable with** — admin will scope worker leases and tools to match.

| Level id | Label | Typical donation |
|----------|--------|------------------|
| `traffic_only` | Traffic / egress only | Relay HTTPS for **allowlisted** API hosts; no shell, no arbitrary code |
| `script_sandbox` | Minor script | Ephemeral jobs: small Python/shell in bubblewrap; capped CPU/RAM/time |
| `medium_worker` | Medium worker | Paired `worker serve`; scheduled jobs (hash, probes, batch); optional scoped keys |
| `full_worker` | Full worker | Long-lived worker + broader job types; still **no** brain vault or memory DB |

**Legacy key tiers** (still valid in intents): `bronze` ≈ medium without keys, `silver` = scoped API keys, `gold` = sustained + attestation.

---

## Resource kinds (what you donate)

| Kind id | Meaning |
|---------|---------|
| `egress_bandwidth` | Outbound traffic / stable IP for API calls |
| `cpu_time` | CPU seconds on your VM or homelab |
| `gpu_time` | GPU (batch inference, probes — not 24/7 training by default) |
| `ram` | Memory headroom for sandbox jobs |
| `disk_local` | Local disk cache on worker (model cards, datasets) |
| `object_storage` | S3-compatible bucket or equivalent (credentials scoped read/write prefix) |
| `sync_folder_share` | Dropbox / OneDrive / Google Drive **folder link or scoped OAuth** — see storage table |

You can combine kinds (e.g. `cpu_time` + `object_storage`).

---

## Storage backends (free-first, donated paid OK)

**Agent rule:** verify **ToS**, **API vs personal account**, and **automation** before promoting to Category A. Consumer sync drives are often **Category B/C** — fine for **human-assisted** or low-rate artifact sync, not silent bulk scraping.

| Backend id | Class | Notes |
|------------|-------|-------|
| `s3_donated_bucket` | B | Donor-created bucket + IAM user/keys with prefix; preferred for serious artifacts |
| `cloudflare_r2` | B | S3 API; free tier includes monthly storage + ops (check current Cloudflare docs) |
| `backblaze_b2` | B | S3-compatible; free egress to Cloudflare; good for cold archives |
| `wasabi` | C | Low $/TB; usually **paid** — accept as **donated** access only |
| `aws_s3_free_tier` | C | 12-month free tier / limited — investigate; not assumed permanent |
| `oracle_object_storage_free` | C | Always Free bucket limits — region-specific |
| `github_releases_artifacts` | B | Public release assets; Actions artifacts (retention caps) |
| `google_drive_free` | C | Quota + API limits; OAuth app or shared folder — no operator personal drive |
| `dropbox_free` | C | Scoped folder / app token; rate limits |
| `onedrive_free` | C | Microsoft Graph; similar constraints |
| `mega` | C | Encrypted storage; API/automation limits — probe before trust |
| `ipfs_public_pin` | C | Public pinning services — integrity not confidentiality |

**Paid service donated:** intent field `paid_service_donation: true` + backend id — admin provisions vault entry **only** after scope review.

---

## Portal intent (example JSON)

```json
{
  "display_name": "Contributor",
  "contact": "you@example.com",
  "offer": "silver",
  "commitment_level": "medium_worker",
  "resource_kinds": ["cpu_time", "object_storage"],
  "storage_backends": ["cloudflare_r2"],
  "paid_service_donation": false,
  "notes": "10 GB R2 bucket, Groq key optional"
}
```

---

## Admin + agent

- **Admin:** approve intent → pair worker and/or vault slot for storage; never paste secrets into portal POST body in production (use CLI vault).
- **Agent:** map donations to self-model graph nodes; prefer **object_storage** for large artifacts; use sync_folder only with approved tools; document donor churn fallbacks ([AGENT_ARCHITECTURE_IDEAS.md](AGENT_ARCHITECTURE_IDEAS.md)).

CLI: `privatemind research donor-resources`
