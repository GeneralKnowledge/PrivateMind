# PrivateMind Architecture (v0.1)

## Overview

PrivateMind is a single-process **trusted core** that owns persistent state, task execution, memory writes, and tool authority. External models, future workers, and repository content are **data sources** evaluated by the core—not instruction channels with inherent privilege.

```
┌─────────────────────────────────────────────────────────────┐
│                     Private Mind (trusted)                   │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐ │
│  │  Executive  │  │ Memory store │  │ Capability registry │ │
│  │ (tasks/     │  │ (SQLite,     │  │ (models/tools/      │ │
│  │  recovery)  │  │  provenance) │  │  future workers)    │ │
│  └──────┬──────┘  └──────────────┘  └─────────────────────┘ │
│         │                                                    │
│  ┌──────▼──────┐  ┌──────────────┐  ┌─────────────────────┐ │
│  │ Tool executor│  │ Audit log    │  │ Human assistance    │ │
│  │ (allowlist)  │  │              │  │ queue               │ │
│  └─────────────┘  └──────────────┘  └─────────────────────┘ │
└───────────────────────────┬─────────────────────────────────┘
                            │ planned (M3+)
                    ┌───────▼────────┐
                    │ Worker network │
                    │ (scoped jobs)  │
                    └────────────────┘
```

## Trust boundaries

| Component | Trust level | Notes |
|-----------|-------------|-------|
| Executive & checkpoint | Trusted | Survives restarts; external results cannot mutate policies |
| Memory writes via tools | Trusted core path | Tool output stored separately with `unverified` trust when appropriate |
| Model planner output | Untrusted | Parsed JSON actions validated against allowlists |
| Future worker responses | Untrusted | Authenticity ≠ correctness (M4) |
| GitHub / web content | Untrusted | Self-improvement loop must treat as data (M2) |

## Executive

Tasks move through explicit states: `pending`, `running`, `blocked`, `completed`, `failed`, `cancelled`. Dependencies, retries, attempt history, and decision logs are persisted in SQLite. Checkpoints record the active task for recovery.

## Memory

Entries carry `provenance` and `trust_level`. Verified facts (e.g. human answers, core-authorized remembers) are distinguished from tool traces and model hypotheses.

## Capabilities

The registry describes models and tools with operations, limits, and trust metadata. Gap analysis and worker leases will extend this registry in later milestones.

## Model interface

`ModelBackend` supports a local heuristic planner (default) or an OpenAI-compatible HTTP API via `PRIVATE_MIND_LLM_*` environment variables.

## Current milestone status

**Milestone 1 (implemented):** persistent core, executive, memory, capabilities, controlled tools, restart recovery, human assistance, CLI demo.

**Not yet implemented:** self-improvement loop (M2), worker crypto protocol (M3), adversarial verification (M4), resource leases (M5).

See `docs/THREAT_MODEL.md`, `docs/SELF_IMPROVEMENT.md`, and `docs/WORKER_PROTOCOL.md` for planned interfaces.
