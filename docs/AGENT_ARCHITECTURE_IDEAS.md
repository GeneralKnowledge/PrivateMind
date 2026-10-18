# Architecture ideas (for the agent to consider)

**Audience:** The executive. **Not a roadmap** — patterns you may **evaluate**, **document**, and **propose** (draft PR, limitation entries, assistance requests). The operator and **contributors** are not expected to implement a central design upfront.

**You choose the structure.** These rows are prompts for thinking, not a fixed topology.

**Floors still apply:** vault on the brain, verified workers, no auto-merge to `main`, respect provider **ToS** and **law**. This is about **sharding work and secrets across donated capacity**. **Keys and secrets should stay movable** (vault ↔ donor, donor ↔ donor). What is **not** in scope is **rotating egress IPs** to dodge abuse bans or ToS — stable donor IPs are normal; moving keys is normal.

---

## Donor servers + API keys (primary model)

A **contributor donates a machine** and optionally **API keys** for specific services (Groq on box A, Brave on box B). That machine should **run the calls for those keys** — keys stay colocated with the egress IP the provider sees.

| Idea | Why consider it | Notes |
|------|-----------------|-------|
| **Key affinity** | Groq key on donor server A → only A calls Groq; quotas and IP limits stay isolated | Map in worker/contributor metadata (operation or provider tags) |
| **No monolith egress** | Avoid one “proxy box” running **every** API — spreads load, blast radius, and rate limits | Scheduler picks worker with matching keys + lease |
| **Keys movable (expected)** | Keys live in the **central vault** *or* on a donor; **move freely** when topology changes — including onto a server that had no keys | Operator/contributor action; audit moves; affinity is *where calls run now*, not a permanent lock |
| **Server without keys** | Donor adds compute first; operator later pushes scoped secrets for one provider | Good for untrusted or fresh VPS before trust rises |
| **Stable donor IP** | Each donor has a **fixed egress**; you **route** jobs to the donor that holds the key | Do **not** treat IP pool hopping as a fix for throttling or bans |

This extends the existing **worker / contributor / lease** story ([WORKER_PROTOCOL.md](WORKER_PROTOCOL.md), M5 scheduling): think **provider-scoped workers**, not one generic proxy.

---

## Brain vs donor roles

| Role | Typical job |
|------|-------------|
| **Brain (trusted core)** | Tasks, memory, vault *or* key catalog, scheduling, verification |
| **Donor worker** | Executes approved outbound tool/API for **its** keys; mTLS to brain; no full memory DB |
| **Body (operator server)** | Same as donor if operator-owned; may hold subset of keys |

Routing rule of thumb: **if the worker doesn’t hold the key for provider P, don’t send P’s jobs there** (unless design explicitly uses forward-proxy with injected bearer — still one hop, one stable IP).

---

## Supporting patterns (optional)

| Idea | Use when |
|------|----------|
| **mTLS brain → worker → API** | Brain never calls cloud directly; worker sandbox runs HTTP |
| **Caching GET on the worker that owns the key** | `/v1/models`, SERP metadata — fewer billable calls on *that* quota |
| **Regional donor** | EU donor for OVH/sovereignty APIs; document region in contributor profile |
| **Failover across donors** | Two donors both have Groq keys → scheduler + reputation; not IP tricks |
| **Egress allowlist on donor** | `iptables`/bubblewrap: worker may only reach hostnames tied to its keys |

When a call fails, order: **limitation log → correct worker selected? → key on that box? → official quota docs** — not “rotate IP.”

---

## Donor capacity is voluntary (do not over-rely)

Shared donors are **gifts**, not guaranteed infrastructure. A contributor may **revoke or rotate keys**, **power off**, or **withdraw** the machine at any time.

| Habit | Why |
|-------|-----|
| **No single point of capability** | If one donor is the only path to Groq/Brave/etc., plan redundancy: operator-owned keys, a second donor, another provider tier, or vault-held fallback |
| **Assume churn** | Track **who** donated **which** key/worker; health-check leases; degrade gracefully when a donor disappears |
| **Prefer operator-owned for critical path** | Long-running identity, billing, or “must work” APIs should not depend only on a stranger’s box unless explicitly accepted risk |
| **Document dependency** | Limitation/memory: *“Category A Groq currently only on donor X — no fallback.”* Then close the gap |

Donors **rotating their own API keys** is normal (quota, security); that is **not** ban-evasion IP rotation — update vault/routing and re-probe.

---

## Identity and networking (related)

- **Agent-only hostnames** — DNS on a domain the operator owns; worker terminates TLS for webhooks (assistance, email inbound).
- **Split horizon** — internal services on LAN; donors touch public APIs for their keys only.

---

## Data and cost

- **Local mirror on donor** — model cards, small caches on the machine that pays the API bill.
- **Failover chain across providers** — different keys on different donors: Groq donor → OVH anon on operator body → `:free` aggregator.

---

## What not to treat as “clever architecture”

- **Egress IP rotation** or pool hopping to evade abuse bans or ToS (distinct from **moving API keys** or donors changing keys).
- One compromised donor holding **all** keys because “it’s the proxy.”
- Scraping logged-in operator sessions.
- Hiding payments or sends from the operator or audit log.

---

## How to use this doc

1. When planning tools or worker jobs, ask: **which donor owns this key right now?** and **what happens if they leave?**
2. Propose topology in a design note or assistance request: *“Contributor X donates ARM box; operator loads Brave key there only; scheduler tag `provider=brave_search`; operator vault holds backup Brave key on body if X drops.”*
3. Iterate — move keys between vault and donors as needed; document the live map in limitation/memory, not in code constants.

See also [AGENT_CAPABILITY_MANDATE.md](AGENT_CAPABILITY_MANDATE.md), [AGENT_MIND_LAYERS.md](AGENT_MIND_LAYERS.md) (self-map: when to use which worker/service), [DEDICATED_SERVER.md](DEDICATED_SERVER.md), [WORKER_PROTOCOL.md](WORKER_PROTOCOL.md), [IDEAS_FOR_THE_AGENT.md](IDEAS_FOR_THE_AGENT.md).
