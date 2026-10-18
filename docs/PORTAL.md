# Resource portal (local server)

The **portal** is a small **local Python HTTP server** on the brain (or operator) host. It is the human-facing entry for:

- Reading **role-based instructions** (admin, donor, helper)
- Submitting a **donor intent** (compute, keys, or both) — skeleton queue for you to approve in CLI
- Glancing at **public-safe status** (setup level, no secrets)

It does **not** replace the vault, worker mTLS, or merge authority. It is **instruction + intake**, not auto-provisioning.

---

## Start

```bash
privatemind portal serve
# default http://127.0.0.1:8780
privatemind portal serve --host 0.0.0.0 --port 8780   # LAN only if you understand firewall risk
```

Open the root URL in a browser. API docs are linked from the home page.

---

## Roles

| Role | How they interact |
|------|-------------------|
| **Primary admin** | First boot: [FIRST_BOOT_ADMIN.md](FIRST_BOOT_ADMIN.md). Uses CLI for vault, wake, merge, pairing. |
| **Donor** | Portal home → donor instructions → submit intent. Admin runs `privatemind portal intents list` and pairs worker per [WORKER_PROTOCOL.md](WORKER_PROTOCOL.md). |
| **Helper (no infra)** | Portal helper page; non-key tasks (review, repro). Agent maintains playbooks under `docs/helpers/`. |

Agent-written detail: [DONOR_AND_HELPER_INSTRUCTIONS.md](DONOR_AND_HELPER_INSTRUCTIONS.md).

---

## API skeleton (v1)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | HTML hub |
| GET | `/instructions/admin` | First-boot admin markdown (rendered plain) |
| GET | `/instructions/donor` | Donor getting started |
| GET | `/instructions/helper` | Helper getting started |
| GET | `/instructions/donor-resources` | Commitment levels, CPU/GPU/storage, S3 & sync drives |
| GET | `/api/v1/donor/catalog` | JSON menu: levels, `resource_kinds`, `storage_backends` |
| GET | `/api/v1/status` | JSON: readiness level, portal version, intent count |
| POST | `/api/v1/donor/intent` | See [DONOR_RESOURCE_TIERS.md](DONOR_RESOURCE_TIERS.md) — `offer` required; optional `commitment_level`, `resource_kinds[]`, `storage_backends[]`, `paid_service_donation` |
| GET | `/api/v1/donor/intents` | List intents (admin; localhost only by default) |

Intents append to `{data_dir}/portal/donor_intents.jsonl`. **You** approve before any worker pairing or key placement.

---

## Hardening (your responsibility)

- Default **bind 127.0.0.1** — use SSH `-L 8780:127.0.0.1:8780` for remote admins.
- Put **TLS + auth** in front (Caddy, nginx) before exposing on the public internet.
- Future: signed contributor tokens — not in v1 skeleton.

Config skeleton: [data/portal_config.json](data/portal_config.json).

---

## CLI

```bash
privatemind portal serve [--host] [--port]
privatemind portal intents list
privatemind portal admin-note --text "…"
```
