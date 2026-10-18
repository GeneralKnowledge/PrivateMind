# Runtime control (human now → executive later)

**Audience:** Primary admin and **executive**.

Today **you** run install, `mode set`, and `portal serve`. The design assumes the **bot will eventually operate** most day-two runtime knobs — within the trust floor.

---

## What stays human (always)

| Surface | Why |
|---------|-----|
| Vault passphrase | Never in scripts, portal, or agent prompts |
| Merge to `main` | Production promotion |
| Weakening verification / protected paths | Trust floor |
| First `curl \| bash` on a bare host | You review [scripts/install.sh](../scripts/install.sh) once |

---

## What the executive will control (expected)

Document and implement via **draft PRs**, not silent production edits:

| Surface | Today | Tomorrow (agent) |
|---------|--------|------------------|
| **Operational mode** | `privatemind mode set` | Propose `slow_start`→`production` after checks; respect throttles until promoted |
| **Portal** | Operator starts `portal serve` | Request systemd/template PR; tune bind via `portal_config.json` draft |
| **Donor intents** | JSONL queue | Triage, draft playbooks, graph updates, assistance — not auto-approve keys |
| **Install / upgrade** | `git pull` + pip | Self-improvement branch: bump deps, extend install.sh — **you merge** |
| **Worker pairing** | CLI | Schedule smoke jobs in `test` mode; document donor topology |

The agent should record intent in memory (`system` / limitation) and **`research operational-mode`** before changing posture.

---

## Install script

Operators may bootstrap with:

```bash
curl -fsSL https://raw.githubusercontent.com/GeneralKnowledge/PrivateMind/main/scripts/install.sh | bash
```

The agent may **propose** install.sh changes (Python floor, clone dir, post-init hooks) but must not assume curl pipe runs unattended on the brain without operator review.

---

## Related

- [GRADUATED_AUTONOMY.md](GRADUATED_AUTONOMY.md)
- [OPERATIONAL_MODES.md](OPERATIONAL_MODES.md)
- [PORTAL.md](PORTAL.md)
- [AGENT_MIND_LAYERS.md](AGENT_MIND_LAYERS.md)
