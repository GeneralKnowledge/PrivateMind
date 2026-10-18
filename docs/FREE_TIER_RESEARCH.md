# Free-tier services research (provisional)

**Status:** Research notes for operators and for the agent — not integration commitments. Free tiers **change often**; confirm limits in each vendor console before relying on them. Last reviewed: **2026-10-18**.

PrivateMind is designed so the **trusted core stays on your hardware** (or a VM you control) while optional cloud services supply inference, git hosting, CI, and webhooks. The goal here is **$0 incremental spend** at small scale, stacking free tiers until something is genuinely worth paying for.

---

## Design fit (what PrivateMind already supports)

| Need | Built-in today | Typical free-tier supply |
|------|----------------|---------------------------|
| Planner / LLM | OpenAI-compatible HTTP (`account add-llm`) | Groq, Gemini API, OpenRouter `:free`, local Ollama |
| Git + self-improvement | **SSH git only** (vault `github` account) | GitHub Free (user/org), GitLab Free |
| Draft PRs | `gh pr create --draft` after push | GitHub CLI + free hosting |
| Remote worker (“body”) | mTLS + pairing | Oracle Always Free ARM, GCP e2-micro, home LAN |
| Secrets | Encrypted vault (never in prompts) | N/A — stay local |
| Human alerts | `PRIVATE_MIND_ASSISTANCE_WEBHOOK_URL` | Cloudflare Worker, self-hosted hook |
| Tests in CI | `run_tests` in workspace | GitHub Actions (quota), local pytest |

**Policy reminder:** Prefer **git@** remotes and SSH keys in the vault. Avoid widening scope with GitHub PATs for routine work. HTTP APIs are fine for **inference** and **optional** webhooks when keys live in the vault.

---

## Incremental stacks (no credit card → slightly more setup)

### Tier 0 — Fully local ($0, no signup)

- **Heuristic planner** (default) — demos and deterministic workflows without any API.
- **Self-improvement fixture** — `privatemind improve run-local` with seeded workspace.
- **SQLite executive/memory** — already the core store.
- **Local pytest** — verification in the trusted workflow.

Good for: proving persistence, security boundaries, and worker protocol on localhost.

### Tier 1 — Free accounts, no payment method

| Service | What you get (typical) | PrivateMind use |
|---------|------------------------|-----------------|
| [Groq](https://console.groq.com/) | Free API tier; per-model RPM/RPD/TPM limits; often **no card** | `--base-url` OpenAI-compatible; use small models for high RPD |
| [Google Gemini API](https://ai.google.dev/) | Free tier on select models; limits per **project** in AI Studio | Same; watch data-use policy on free tier |
| [OpenRouter](https://openrouter.ai/) | `:free` models; **50 req/day** (20/min) without purchase; **1000/day** after **$10 lifetime** credits | One key, many models; not $0 if you top up for limits |
| [GitHub Free](https://docs.github.com/en/get-started/learning-about-github/githubs-plans) | Unlimited public/private repos (personal); **2,000 Actions min/mo** on private repos | Dedicated `agent-github` user; push branches only |
| [Cloudflare Workers](https://developers.cloudflare.com/workers/platform/limits/) | **100,000 requests/day**; 10 ms CPU/request on free | Assistance webhook relay, lightweight ingress |

**Planner tip:** Rate-limit aware clients (backoff on HTTP 429) belong in the core eventually; until then, keep task concurrency low.

### Tier 2 — Free “always-on” compute (card may be required; stay within Always Free)

| Service | What you get (typical, 2026 docs) | PrivateMind use |
|---------|-----------------------------------|-----------------|
| [Oracle Cloud Always Free](https://docs.oracle.com/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm) | **2 OCPU / 12 GB** ARM (A1 flex) *or* 2× AMD micro VMs; capacity often scarce | Brain and/or `privatemind worker serve --host 0.0.0.0 --mtls` |
| [Google Cloud free tier](https://cloud.google.com/free) | e2-micro in select regions (always free within limits) | Small worker or backup node |
| **Home / lab PC** | Your hardware | Best “body” for continuity (see `DEDICATED_SERVER.md`) |

Oracle marketing pages sometimes still mention higher ARM quotas; **trust the current [Always Free Resources](https://docs.oracle.com/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm) doc** (e.g. 1,500 OCPU-hours / 9,000 GB-hours per month → ~2 OCPU + 12 GB RAM).

### Tier 3 — Free data & CI adjacency (optional)

| Service | Free slice | Notes |
|---------|------------|--------|
| GitHub Actions | 2,000 min/mo (Free plan, private); **unlimited on public repos** for standard hosted runners | Run pytest on pushed branches; mind artifact storage caps |
| GitHub Codespaces | 120 core-hours / mo (personal Free) | Occasional debugging, not the persistent brain |
| Cloudflare R2 | 10 GB-month, limited ops | Backup artifacts, not live DB |
| Cloudflare D1 / KV | Small daily quotas | Only if the agent adds edge state (keep vault off CF) |
| Neon / Supabase / Turso | Generous dev free tiers | **Not required** — core uses SQLite; use only if the agent chooses to integrate |

Sources: [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions), [Cloudflare developer pricing](https://www.cloudflare.com/plans/developer-platform-pricing/).

---

## Inference comparison (free-first)

| Provider | Billing | Rough free limits | Tradeoffs |
|----------|---------|-------------------|-----------|
| **Local Ollama** | $0 | Hardware-bound | Best privacy; you operate the model |
| **Groq** | $0 tier | Model-specific RPM/RPD/TPM ([docs](https://console.groq.com/docs/rate-limits)) | Fast; limits are org-wide |
| **Gemini API** | $0 tier | Model-specific; view in AI Studio | Strong models; free tier may use prompts for product improvement * |
| **OpenRouter `:free`** | $0 models | 50/day (20/min) default; 1000/day after $10 credits ([limits](https://openrouter.ai/docs/api/reference/limits)) | Aggregator; provider throttling at peaks |
| **Heuristic (built-in)** | $0 | Unlimited | Not general intelligence — good for tests |

\* Gemini free-tier data use is described in [Google pricing/docs](https://ai.google.dev/gemini-api/docs/pricing); use **paid tier** if prompts must not be used for training.

**PrivateMind config example (Groq):**

```bash
privatemind account add-llm \
  --name groq \
  --base-url https://api.groq.com/openai/v1 \
  --model llama-3.1-8b-instant \
  --api-key "$GROQ_API_KEY"
```

---

## GitHub (free tier + agent workflow)

| Feature | Free personal (typical) | Agent usage |
|---------|-------------------------|-------------|
| Private repos | Yes (limited features vs Pro) | Host PrivateMind fork |
| `git push` over SSH | Yes | Self-improvement branches |
| Actions minutes | 2,000 / month private | CI for pytest on branch |
| `gh pr create --draft` | Yes | After trusted workflow push |
| Pages | Public repos | Optional docs site |

**2026 pricing note:** GitHub has been adjusting Actions billing for self-hosted runners ([changelog](https://github.blog/changelog/2025-12-16-coming-soon-simpler-pricing-and-a-better-experience-for-github-actions/)). Standard **GitHub-hosted** usage on **public** repos remains a common $0 CI pattern if you accept a public mirror or public test repo.

---

## Edge & webhooks (assistance notifications)

| Option | Free tier | Fit |
|--------|-----------|-----|
| Cloudflare Worker | 100k req/day | POST from `assistance_webhook_url` → Slack/email bridge you write |
| Self-hosted on brain | $0 | curl to local ntfy.sh instance (open source, can self-host) |
| Discord webhook | Free | Simple operator channel |

Keep webhook payloads **redacted** — the core should not exfiltrate vault material (today: question + context dict only; review what tasks put in `context`).

---

## Search & tools (if the agent requests them later)

| Service | Free slice | Agent note |
|---------|------------|------------|
| Brave Search API | Limited free queries/month | Store key in vault; wrap via approved tool runner |
| Tavily / similar | Trial credits | Treat as consumable; record limitations |
| Hugging Face Inference | Free tier with rate limits | Good for narrow models; verify ToS for automation |

Prefer **approved tool + sandbox** (`tool-request approve --runner-arg`) over baking vendor SDKs into the trusted core.

---

## Risks and operator hygiene

1. **Credit cards on “free” cloud** — Oracle/GCP can charge if you create non–Always Free shapes. Use budgets, tags, and compartment quotas.
2. **API key leakage** — Only vault + scrubbed sandbox env (see `tools/sandbox.py`).
3. **Automation ToS** — GitHub and LLM providers restrict abuse; dedicated agent accounts contain blast radius.
4. **Rate limits** — Design for 429 backoff; self-improvement is bursty, not chat-scale.
5. **Free tier drift** — Re-check limits quarterly; link this doc from agent ideas, not hardcoded constants in code.

---

## Suggested $0 “powerful enough” layout

```text
[Oracle ARM Always Free or home server]
  ├── privatemind core + vault + SQLite
  ├── git clone over SSH (GitHub Free)
  ├── optional: worker serve mTLS on same or second free VM
  └── Ollama OR Groq/Gemini for planning (vault LLM account)

[GitHub]
  ├── agent-github SSH key (vault)
  ├── feature branches + draft PRs (gh)
  └── Actions: pytest on push (optional)

[Cloudflare Worker] (optional)
  └── assistance webhook → your phone/Slack
```

The agent can **propose** swapping components (e.g. add Neon, change model router, harden sandbox with bubblewrap) via self-improvement — see [IDEAS_FOR_THE_AGENT.md](IDEAS_FOR_THE_AGENT.md).

---

## What we deliberately did not research deeply here

- Enterprise contracts, reserved instances, or “almost free” paid tiers.
- Crypto/faucet-style APIs (unreliable, often ToS-violating for agents).
- Scraping-as-a-service without explicit API keys.

Add more rows via PRs or agent-driven doc updates when you validate a service in production.
