# Operational modes (slow start / test / production)

Control how aggressively the executive runs and how fast **external probes/APIs** fire while you set up or trial **new workers**.

**Not a security boundary** — vault, verification, and merge rules still apply. This is **throttling and posture** for operators and donors.

**Future:** the **executive** is expected to propose and manage mode transitions (e.g. stay in `slow_start` until graph checks pass) — you keep override via env/file. See [AGENT_RUNTIME_CONTROL.md](AGENT_RUNTIME_CONTROL.md).

Presets: [`data/operational_mode_presets.json`](data/operational_mode_presets.json).

---

## Modes

| Mode | When to use |
|------|-------------|
| **`slow_start`** | First boot, new vault, learning the assistance queue — default after `privatemind init` |
| **`test`** | New worker paired, staging tool, rehearsal — lowest API/worker budgets |
| **`production`** | Stable brain; still subject to free-tier entitlements and agent “food” discipline |

---

## Operator controls

```bash
privatemind mode status
privatemind mode set slow_start   # or test | production
```

Environment override (wins over file):

```bash
export PRIVATE_MIND_OPERATIONAL_MODE=test
```

File override (persists): `{data_dir}/operational_mode.json`

```json
{ "mode": "slow_start", "notes": "Until first merge", "test_worker_fingerprints": ["abc…"] }
```

---

## What changes per mode

| Knob | slow_start | test | production |
|------|------------|------|------------|
| Max steps per `tick` | capped (2) | capped (3) | high (50) |
| `wake --run` / idle loop iterations | capped | lower | normal |
| `research probe-*` minimum interval | 120s | 60s | none |
| Documented API budget multiplier | 0.25 | 0.10 | 1.0 |
| New worker policy | smoke jobs only | smoke jobs only | normal leases |

The agent should read `mode status` on wake and **not fight** throttles — use maintain/reflect modes instead of hammering APIs ([AGENT_MIND_LAYERS.md](AGENT_MIND_LAYERS.md)).

---

## First boot

Stay on **`slow_start`** until `setup-check` is stable and you have run a few manual `tick --steps 1` cycles. Switch to **`test`** when pairing a **new node**; return to **`slow_start`** or **`production`** when satisfied.

See [FIRST_BOOT_ADMIN.md](FIRST_BOOT_ADMIN.md).

---

## CLI

```bash
privatemind mode status
privatemind mode set production
privatemind research operational-mode    # JSON presets for the agent
```
