# PrivateMind

An open-source autonomous agent with a **private trusted core**: persistent executive, memory with provenance, capability registry, and controlled tools. Designed to grow toward secure distributed workers and measured self-improvement without exposing internal state.

## Quick start

Requirements: Python 3.11+

```bash
cd /path/to/PrivateMind
python -m pip install -e ".[dev]"
privatemind init
privatemind demo --run
privatemind status
privatemind memory-search --kind fact
```

Data defaults to `~/.privatemind/mind.sqlite3`. Override with `--data-dir` or `PRIVATE_MIND_DATA_DIR`.

### Optional remote model

Set OpenAI-compatible inference:

```bash
export PRIVATE_MIND_LLM_BASE_URL="https://api.openai.com/v1"
export PRIVATE_MIND_LLM_API_KEY="sk-..."
export PRIVATE_MIND_LLM_MODEL="gpt-4o-mini"
```

Without these variables, a local **heuristic planner** runs the milestone demo offline.

## CLI

| Command | Purpose |
|---------|---------|
| `privatemind init` | Create database and seed capabilities |
| `privatemind demo --run` | Milestone 1 end-to-end demo |
| `privatemind task "..."` | Enqueue work |
| `privatemind tick --steps N` | Run executive steps |
| `privatemind status` | Tasks, checkpoint, pending help requests |
| `privatemind help-request "..."` / `help-answer ID TEXT` | Human assistance |
| `privatemind capabilities` | List registered capabilities |

## Architecture

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — components and trust boundaries
- [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) — adversaries and guarantees
- [docs/SELF_IMPROVEMENT.md](docs/SELF_IMPROVEMENT.md) — planned M2 workflow
- [docs/WORKER_PROTOCOL.md](docs/WORKER_PROTOCOL.md) — draft worker/lease protocol
- [docs/STATUS.md](docs/STATUS.md) — what works today vs roadmap

## Development

```bash
pytest
```

## Roadmap milestones

1. **Persistent autonomous core** — implemented in v0.1
2. Self-improvement loop (repo access, PRs)
3. Secure worker communication
4. Untrusted result verification
5. User-contributed resources with revocable leases
6. Adaptive resource management
7. Gradual autonomy expansion with explicit threat models

## License

MIT (add `LICENSE` file when the project owners choose formal licensing.)
