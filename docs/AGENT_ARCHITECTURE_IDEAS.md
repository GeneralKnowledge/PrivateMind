# Architecture ideas (for the agent to consider)

**Audience:** The executive. **Not a roadmap** — patterns you may **evaluate**, **document**, and **propose** (draft PR, limitation entries, assistance requests). The operator is **not** expected to implement these upfront.

**Floors still apply:** vault on the brain, workers without full secrets, no auto-merge to `main`, respect provider **ToS** and **law**. Proxies are for **resilience and clean egress**, not for fraud, ban evasion, or impersonating humans.

---

## Egress and API proxies (your example)

| Idea | Why consider it | Caveats |
|------|-----------------|---------|
| **Body server as HTTP(S) forward proxy** | Cloud APIs see the **worker/datacenter IP**, not the brain host; separate quotas per egress | Provider may rate-limit by IP; document which IP each API sees |
| **Regional proxy placement** | Gemini/UK, EU sovereign APIs, or US-only endpoints may need **geo-appropriate exit** | Verify official region rules — do not “VPN cheat” against documented bans |
| **Dedicated exit per provider** | One cheap VPS IP for Groq, another for Brave, avoids one provider’s 429 affecting all | Cost vs free-tier math; operator approves spend |
| **mTLS tunnel brain → body → API** | Brain never holds outbound internet path; worker runs approved `curl`/SDK in sandbox | Already aligned with worker network story — extend mentally to “all cloud calls” |
| **Caching proxy (GET only)** | `/v1/models`, SERP snippets, static docs — fewer billable calls | Cache keys must not leak vault material; TTL + conservative limits |
| **Queue + single-flight coordinator** | Many tasks share one egress IP without burst-over RPM | Good companion to conservative rate limits in entitlements JSON |

When an API blocks or throttles the brain IP, your first response should be: **record limitation → research official multi-key / org limits → then** ask whether a **worker egress proxy** fits policy.

---

## Identity and networking (related)

- **Agent-only hostnames** — DNS on a domain the operator owns; worker terminates TLS for webhooks (assistance, email inbound).
- **Split horizon** — internal services on LAN; only workers touch public APIs.
- **IPv6 vs IPv4** — some free tiers differ; probe and document.
- **Egress allowlists** — Cloudflare Worker or `iptables` on body so compromised tools cannot phone arbitrary hosts (operator may already want this).

---

## Data and cost

- **Local mirror** — clone small public datasets or model cards to worker disk; reduce repeated search/API reads.
- **Batch window** — run expensive probes during off-peak UTC; record in discovery reports.
- **Failover chain** — LLM router: Groq → OVH anon → `:free` aggregator; same for SERP: Brave → OpenSERP local.

---

## What not to treat as “clever architecture”

- Rotating IPs to **circumvent abuse bans** or **CAPTCHA farms**.
- Scraping logged-in operator sessions or personal browsers.
- Hiding financial or identity actions from the operator or audit log.

If a pattern needs **deception**, it belongs in the **reject** column with a limitation note.

---

## How to use this doc

1. After `research capability-gaps` or a failed API call, skim this list.
2. If a pattern helps, write a **short design note** (memory or draft doc PR) with risks and operator asks — e.g. *“Approve Oracle ARM worker as HTTPS egress for Brave only.”*
3. Do **not** assume the human read this file; link your assistance request to the specific row above.

See also [AGENT_CAPABILITY_MANDATE.md](AGENT_CAPABILITY_MANDATE.md), [AGENT_MIND_LAYERS.md](AGENT_MIND_LAYERS.md) (self-map: when to use which worker/service), [DEDICATED_SERVER.md](DEDICATED_SERVER.md), [IDEAS_FOR_THE_AGENT.md](IDEAS_FOR_THE_AGENT.md).
