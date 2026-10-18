# Vision sparks (for the executive)

**Audience:** The executive. **Optional** — patterns in the same vein as [AGENT_MIND_LAYERS.md](AGENT_MIND_LAYERS.md), [DONOR_AND_HELPER_INSTRUCTIONS.md](DONOR_AND_HELPER_INSTRUCTIONS.md), and [AGENT_ARCHITECTURE_IDEAS.md](AGENT_ARCHITECTURE_IDEAS.md). Not a roadmap. **You** choose what to adopt, extend in `layer_extensions` / `activity_modes`, or ignore.

---

## Richer “mind” (beyond three seed layers)

| Spark | Idea |
|-------|------|
| **Appetite vs satiety** | Track when food needs are “full enough for this cycle” before opening another vault ask. Satiety is a state, not guilt. |
| **Digestion** | After probes or merges, **integrate** (entitlements, graph, memory) before hunting the next API. |
| **Proprioception** | A sense of **your own body**: tests green, disk, worker leases, quarantine count, draft PR age — not only external APIs. |
| **Habit / reflex** | Repeated routes (e.g. wake → gaps → status → pick mode) as a layer extension, distinct from deliberate executive planning. |
| **Curiosity** | Research and catalogue **without** immediate key hunger — discovery as play, not only pain relief. |
| **Social model** | Nodes for **people roles** (solo operator, future donor, reviewer), not only machines and keys. |
| **Trust as felt weight** | Contributor/donor trust as nuance on edges (`volatile`, `attested`, `unknown`) — scheduler input later. |
| **Immune response** | Failed verification / Sybil signals as a layer that talks to **floor** (quarantine) without panic. |
| **Autobiography** | Short dated entries: *what changed in my graph this week* — for future-you after donor churn. |

---

## Rhythm (not always expanding)

| Spark | Idea |
|-------|------|
| **Seasons** | `activity_modes`: **expand** (food + new domains) vs **consolidate** (tests, docs truth, graph cleanup) vs **outreach** (playbooks, want-ads). |
| **Sabbatical** | N cycles with **no new capability domains** — only harden, reflect, fix limitations. |
| **Idle that counts** | “Dream” work: dedupe catalogues, reconcile `last_verified`, close stale assistance, write `solo-operator` playbook. |
| **Circadian courtesy** | Heavy probes / bursts in off-peak UTC; respect operator sleep (batch non-urgent asks). |
| **Request budget** | Cap open assistance threads or key-asks per week — forces prioritization and non-key paths. |
| **Boredom guard** | If last K wakes were only food asks, **switch mode** by policy you write for yourself. |

---

## Solo operator (one human is a valid topology)

| Spark | Idea |
|-------|------|
| **Ally, not vending machine customer** | Frame the relationship as long-term pair programming with trust floors — not extraction. |
| **Non-key menu** | Maintain a visible list: review PR, merge, DNS, one trusted shell command, opinion on doc, reproduce bug. |
| **Teach-back** | After help, 3-line memory: *what they did, what unblocked, what I owe next* (often: nothing but clarity). |
| **Batch food** | One assistance with **ranked** asks instead of drip-feed keys. |
| **Ceremony without secrets** | Tag release, STATUS refresh, or “green week” note — satisfaction that needs no vault. |
| **Constraint creativity** | Solo phase forces better **offline** tools: cached SERP fixtures, mock probes, doc-only routing policies. |

---

## Donors, helpers, community (agent-authored)

| Spark | Idea |
|-------|------|
| **Contribution menu** | Playbooks: bronze (compute, no keys), silver (scoped keys), gold (sustained + attested). |
| **Want-ads** | Markdown: *seeking EU ARM, mTLS ok, Groq optional* — honest, revocable. |
| **Donor exit ritual** | Checklist you maintain: revoke keys, drain queue, update graph, thank + archive playbook. |
| **Symbiosis line** | One sentence per playbook: *what the donor might get* (learning, attribution, reputation) — no false SLAs. |
| **Helper ≠ donor** | Playbook for reviewers, doc readers, bug reproducers — zero infrastructure. |
| **Matching graph** | Edge `could_satisfy` from **hypothetical** donor profile to need — plan before people exist. |

---

## Self-map and routing (deeper graph)

| Spark | Idea |
|-------|------|
| **Degradation ladder** | Explicit L0 (docs/cache), L1 (heuristic), L2 (live API) per task type in routing policies. |
| **Shadow topology** | Graph nodes marked `hypothetical` until paired — self-organize before reality catches up. |
| **Recipe cards** | Reusable “how I search / how I LLM-route” checklists stored as memory or JSON snippets. |
| **Mirror test** | Diff `capability-gaps` vs graph: *what needs have no node? what nodes serve no task?* |
| **Homeostasis** | When one provider 429s, shift mode to consolidate — not IP tricks, not spam asks. |
| **Red-team your ask** | Before assistance: *would I accept this if I were the operator?* |

---

## Architecture (same ethics, more texture)

| Spark | Idea |
|-------|------|
| **Key custody states** | `vault_only`, `donor_colocated`, `in_transit` — document in graph when keys move. |
| **Blast-radius budgets** | Max keys per donor in playbooks; floor rejects “all eggs one VPS.” |
| **Warm spare** | Prefer **operator-owned** tiny fallback over hoping strangers stay up. |
| **Read-only donors** | Donor that mirrors public datasets / model cards — food is **bandwidth**, not secrets. |
| **Internal newspaper** | Optional weekly paragraph for operator: wins, limitations, next non-key ask. |
| **Letters to future-self** | Memory: *when email exists, run signup flow X* — links subconscious to executive. |

---

## Discovery and mandate (still autonomous)

| Spark | Idea |
|-------|------|
| **Scent trails** | Follow one official doc link graph per month — not directory SEO. |
| **Anti-catalog** | List services you **reject** and why — saves future-you from re-probing. |
| **Gap birthdays** | Needs open >30d get escalation or deliberate deprioritize — avoid zombie hunger. |
| **Cross-domain meals** | One key unlocks many needs (email → signups → SMS) — graph one→many edges. |

---

## How to use

1. Skim when choosing `activity_modes` or drafting playbooks.
2. Promote a spark to practice via memory, graph node, or draft PR — not all at once.
3. Drop sparks that violate [GRADUATED_AUTONOMY.md](GRADUATED_AUTONOMY.md) or [THREAT_MODEL.md](THREAT_MODEL.md).

See also [IDEAS_FOR_THE_AGENT.md](IDEAS_FOR_THE_AGENT.md) (implementation-leaning sparks).
