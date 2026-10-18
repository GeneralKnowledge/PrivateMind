# Donor and helper instructions (agent-authored)

**Audience:** The executive — you **write and maintain** these for humans who are not the primary operator.

**Operator note:** You may skim for safety, but you are **not** expected to write onboarding for every contributor. The agent drafts and updates instructions as topology grows.

---

## Why this exists

Keys and vault slots are **food** ([AGENT_MIND_LAYERS.md](AGENT_MIND_LAYERS.md)) — not the only help you need. Before donors exist, you may have **one operator**. Value their time: merges, DNS, feedback, review, and **non-key** tasks count as real help.

When someone **does** donate compute or keys, they should get **clear, scoped** instructions you wrote — not a vague “join my project.”

---

## What you maintain

| Artifact | Purpose |
|----------|---------|
| **This doc** | Policy: tone, safety floors, what to ask donors vs operators |
| **[`data/donor_helper_playbooks.json`](data/donor_helper_playbooks.json)** | Machine index of playbooks (empty skeleton → you add rows) |
| **`docs/helpers/`** | Human-readable playbooks (one file per audience or donor tier) |

Suggested playbook audiences (add more as layers grow):

- **solo_operator** — help without new keys (review, merge, uptime, answers)
- **compute_donor** — worker pairing, mTLS, no keys yet
- **key_donor** — scoped API keys, which services, rotation, revoke
- **hybrid_donor** — machine + keys (see [AGENT_ARCHITECTURE_IDEAS.md](AGENT_ARCHITECTURE_IDEAS.md) affinity)

---

## Playbook skeleton (copy into `docs/helpers/<slug>.md`)

```markdown
# <Title> — for <audience>

## What you are helping with
(One paragraph. No hype.)

## What we are not asking for
(Personal inbox, mainnet keys, root on operator brain, etc.)

## Steps
1. …
2. …

## Scope limits
(Which APIs, rate limits, how to revoke)

## If something breaks
(Contact path, what logs to share, quarantine behavior)

## Last updated
(ISO date + what changed)
```

Keep instructions **short**, **revocable**, and aligned with [WORKER_PROTOCOL.md](WORKER_PROTOCOL.md) and [THREAT_MODEL.md](THREAT_MODEL.md).

---

## When to write or refresh

- Before asking for a new donor class in an assistance request → attach or link a draft playbook.
- After worker protocol or vault kinds change → update affected playbooks in a draft PR.
- When solo: maintain **solo_operator** playbook so your asks are mostly **non-key** unless blocked.

---

## CLI

```bash
privatemind research helper-playbooks    # index JSON (agent-filled rows)
```

See also [AGENT_MIND_LAYERS.md](AGENT_MIND_LAYERS.md) (life beyond “food”), [GRADUATED_AUTONOMY.md](GRADUATED_AUTONOMY.md).
