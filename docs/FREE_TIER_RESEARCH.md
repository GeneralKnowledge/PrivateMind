# Free-tier services research (provisional)

**Status:** Research notes for operators and for the agent — not integration commitments. Free tiers **change often**; confirm limits in each vendor console before relying on them. Last reviewed: **2026-10-18**.

Many valuable allowances are **under-documented** (buried in product docs, notebook UI, or intro pricing). The agent should **actively hunt** for these — see [How to research hidden / cheap options](#how-to-research-hidden--cheap-options) — and append verified rows here with source links and dates.

PrivateMind is designed so the **trusted core stays on your hardware** (or a VM you control) while optional cloud services supply inference, git hosting, CI, and webhooks. The goal here is **$0 incremental spend** at small scale, stacking free tiers until something is genuinely worth paying for.

---

## Design fit (what PrivateMind already supports)

| Need | Built-in today | Typical free-tier supply |
|------|----------------|---------------------------|
| Planner / LLM | OpenAI-compatible HTTP (`account add-llm`) | Groq, Gemini, NIM, OpenRouter `:free`, Kilo/Aion/LLM7/ModelScope/SiliconFlow/OVH, local Ollama |
| Multi-provider routing | `privatemind research quota-diff` + catalog | Runtime quota JSON + [free_tier_provider_catalog.json](data/free_tier_provider_catalog.json) |
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

## Under-advertised free compute (easy to miss)

These are **not** wired into PrivateMind by default. They suit **batch** work (training, heavy tests, one-off experiments) more than a 24/7 brain. Check the **account quota UI** — marketing pages often omit the numbers.

| Service | What people miss | Typical allowance (verify live) | PrivateMind angle |
|---------|------------------|--------------------------------|-------------------|
| **[Kaggle Notebooks](https://www.kaggle.com/docs/efficient-gpu-usage)** | GPU quota is in the **notebook editor / profile**, not the homepage | **~30 GPU hours/week** (P100 class); **floating quota** can exceed 30h when capacity allows; resets **Saturday 00:00 UTC**; **20 TPU hours/week** ([TPU docs](https://www.kaggle.com/docs/tpu)) | Approved tool or manual: run training notebooks, export artifacts via Kaggle API; **not** a substitute for persistent `worker serve` |
| **[Google Colab](https://colab.research.google.com/)** | Free tier exists but limits are **session-based** and undocumented in one table | Ephemeral GPU/TPU when available; queues at peak | Same — exploratory only |
| **Kaggle + Colab Pro link** | [2025 blog](https://www.kaggle.com/blog/level-up-your-compute-more-gpu-hours-on-kaggle-wit): linked Colab Pro adds **+15 GPU h/week** on Kaggle; Pro+ **+30** (paid Colab; Kaggle portion still “free” add-on) | Only if operator already pays for Colab | Optional operator boost, not $0 |
| **[Google Cloud codelab credits](https://codelabs.developers.google.com/codelabs/cloud-codelab-credits)** | **No card** learning credits for codelabs | Often **~$300 equivalent for 6 months** on specific redemption flows | Prototype GCP tooling; stay in always-free SKUs where possible |
| **[Paperspace Free GPU](https://www.paperspace.com/)** | Free Gradient tier is easy to overlook | Free GPU notebooks (hardware tier varies); sessions often **auto-stop after ~12h** | Batch ML; watch ToS for automation |
| **[GitHub Codespaces](https://docs.github.com/en/billing/reference/product-usage-included)** | Listed under **product usage included**, not “Pricing hero” | Personal Free: **120 core-hours/month**, **15 GB storage** (2026 docs) | Debug a branch in browser; don’t store vault there |
| **Oracle / GCP “Always Free”** | Hidden in **Always Free Resources** appendix, not signup wizard | See Tier 2 above | Persistent low-cost VM if you secure capacity |

**Kaggle operational tips** (from [efficient GPU usage](https://www.kaggle.com/docs/efficient-gpu-usage)): stop interactive sessions when done (idle timeout burns quota), avoid redundant “Commit” batch runs, prefer **Kaggle API** to push notebook versions without leaving editors open.

### GPU spillover ladder (don’t waste the good stuff)

Use **persistent / high-trust** resources for the brain and workers; push **ephemeral GPU** work down this ladder:

```text
1. Local CPU + heuristic / small models     ← default executive planning
2. Free LLM APIs (Groq, Gemini, NIM hosted) ← chat-scale inference, rate limits
3. Batch GPU notebooks (Kaggle, Paperspace,   ← training, one-off eval, heavy tests
   Colab, GCP codelab credits)
4. Serverless GPU burst (Modal $30/mo, etc.)  ← short jobs, scale to zero
5. Self-hosted NIM on a GPU box               ← when you already pay for the GPU
6. Paid GPU                                   ← only after recording a limitation
```

**Google codelab credits** and **Paperspace** fit tier **3**: spin up, run the job, export artifacts, tear down — not `privatemind wake` 24/7.

Track probes and verdicts: [`FREE_TIER_CANDIDATES.md`](FREE_TIER_CANDIDATES.md), CLI `privatemind research candidate`, `privatemind research probe-api`.

---

## Multi-provider quota file (operator / router)

If you run an external **multi-LLM router** that tracks per-provider RPM/TPM/health, keep its state JSON alongside PrivateMind recon:

| Artifact | Purpose |
|----------|---------|
| [data/free_tier_provider_catalog.json](data/free_tier_provider_catalog.json) | Static map: provider id → base URL, docs, env vars, candidate slug |
| [data/free_tier_quota_state.example.json](data/free_tier_quota_state.example.json) | Shape for runtime counters (`schema_version`: `2026-09-27`) |

**CLI:**

```bash
# List catalog ids (should match your router's provider keys)
privatemind research provider-catalog

# Find keys in your file that are missing from the repo catalog (or vice versa)
privatemind research quota-diff /path/to/your/quota_state.json

# Seed memory candidates for every catalog provider (pending until probed)
privatemind research seed-catalog
```

Provider ids in the catalog today include `sambanova_cloud`, `unorouter`, plus the router set documented in [free_tier_provider_catalog.json](data/free_tier_provider_catalog.json).

When your router adds a new key, append metadata to the catalog and a row in [FREE_TIER_CANDIDATES.md](FREE_TIER_CANDIDATES.md), then re-run `quota-diff`.

### GitHub as the living source of lists

Static docs go stale; **GitHub READMEs** are where the community updates free-provider inventories. PrivateMind ships a curated source list and a scanner:

| File | Role |
|------|------|
| [data/free_tier_github_sources.json](data/free_tier_github_sources.json) | Repos/paths to fetch (`cheahjs/free-llm-api-resources`, `mnfst/awesome-free-llm-apis`, `open-free-llm-api/awesome-freellm-apis`, `xyzs996/free-llm-api`, `bradAGI/awesome-free-inference`, `unorouter/unorouter`) |

```bash
privatemind research github-sources          # show raw URLs
privatemind research github-sync             # fetch READMEs, map mentions → catalog ids
privatemind research github-sync --source-id cheahjs-free-llm
```

**Workflow for the agent:** run `github-sync` periodically → anything in `in_github_lists_not_in_catalog` becomes a research task (probe, then `research candidate` or extend the catalog). Do **not** auto-merge third-party lists into the trusted core; treat them as **hints** verified against official docs.

**SambaNova Cloud** and **UnoRouter** are called out because community lists and operator reports still show them working (Oct 2026); limits and card rules change — probe before relying.

---

## NVIDIA NIM (Inference Microservices)

NIM is easy to miss because it spans **hosted APIs**, **containers**, and **NGC** — not one “free tier” banner.

| Mode | Cost (dev) | What you get | PrivateMind fit |
|------|------------|--------------|-----------------|
| **Hosted API** ([build.nvidia.com](https://build.nvidia.com/)) | Developer program; **OpenAI-compatible**; per-model **RPM** limits ([forums](https://forums.developer.nvidia.com/t/nim-rpm-rate-limit/378937)) | `https://integrate.api.nvidia.com/v1` + key from [settings](https://build.nvidia.com/settings) ([llms.txt](https://build.nvidia.com/llms.txt)) | **`account add-llm`** — same as Groq/Gemini |
| **Downloadable NIM** (Docker/NGC) | Free for research/dev/test on **up to 16 GPUs**; you pay infra ([Run NIM Anywhere](https://docs.api.nvidia.com/nim/docs/run-anywhere)) | Self-host on worker GPU; OpenAI `/v1/chat/completions` on localhost | Pair as **worker** or sidecar; not the SQLite brain |
| **Model-free NIM** | Same dev terms | Container pulls from HF/NGC/S3 ([docs](https://docs.nvidia.com/nim/large-language-models/latest/deployment/model-free-nim.html)) | Advanced worker image — operator setup |
| **Hugging Face serverless NIM** | Selected models | HF API path per NVIDIA docs | Optional approved tool |
| **NVIDIA LaunchPad** | Free browser access to HW for trials ([deployment FAQ](https://docs.api.nvidia.com/nim/docs/deployment)) | Short experiments | Manual; record outcome in research ledger |
| **Production** | **NVIDIA AI Enterprise** license | Support, SLAs, PB branches | Out of scope for autonomous merge |

**Hosted NIM in PrivateMind (operator):**

```bash
export NVIDIA_API_KEY="nvapi-..."   # from build.nvidia.com/settings
privatemind research probe-nim      # lists sample model ids if key works
privatemind account add-llm \
  --name nvidia-nim \
  --base-url https://integrate.api.nvidia.com/v1 \
  --model meta/llama-3.1-8b-instruct \
  --api-key "$NVIDIA_API_KEY"
```

Use **`privatemind research candidate`** to mark `nvidia-nim-hosted` as `useful` or `reject` with notes after a real task attempt.

**Self-hosted NIM** belongs on a **GPU worker**, not inside the trusted core process: run the container on the body machine, point an approved tool or future worker op at `http://127.0.0.1:8000/v1` (mTLS in front if remote).

---

## More candidates (probe, don’t assume)

| Service | Hidden value | Category |
|---------|--------------|----------|
| **[Modal](https://modal.com/pricing)** | **$30/mo** included compute on Starter; pay per second when idle off | gpu/batch |
| **[Replicate](https://replicate.com/)** | Some free runs; mostly pay-per-use | gpu/batch |
| **Hugging Face Inference** | Free tier on select models | llm/gpu |
| **NVIDIA LaunchPad** | Trial enterprise GPUs in browser | gpu/batch |
| **Lightning.ai / Lightning Studio** | Promotional GPU hours (check current) | gpu/batch |
| **E2B / Daytona** | Dev sandbox credits (verify site) | sandbox |
| **Google Colab** | Ephemeral GPU; queue at peak | gpu/batch |
| **Vertex AI free trial** | Separate from Gemini API consumer tier | gpu/batch |

Add rows to [FREE_TIER_CANDIDATES.md](FREE_TIER_CANDIDATES.md) when discovered.

---

## Cheap VPS (not free — often beats “free tier” UX)

When **€1–4/month** is acceptable, European VPS can be **cheaper than brand-name “cloud”** and simpler than fighting Oracle capacity. **Intro prices lie** — always screenshot **renewal** and **setup fees** (e.g. IONOS XS sometimes carries a one-time setup charge in some regions).

| Provider | Why it’s under-discussed vs Hetzner | Typical entry (verify checkout) | Tradeoff vs Hetzner |
|----------|-------------------------------------|----------------------------------|---------------------|
| **[IONOS VPS](https://www.ionos.com/server/vps)** | Heavily **promo-priced** (€1/$2 first term); includes SSL, DDoS, “unlimited” traffic in ads | **~€1–2/mo intro**, **VPS S ~€4** with more NVMe; renewal often **much higher** | Weaker perf/$ at renewal; fine for **single brain** if you watch renewal |
| **[OVH VPS](https://www.ovhcloud.com/)** | “Starter” deals (~€1) appear in forums; not the default Hetzner recommendation | Sub-€2 promos in EU; standard tiers scale up | Support/varies by line (So you Start vs Cloud) |
| **[Netcup](https://www.netcup.com/en/server/vps)** | Less mindshare than Hetzner in English dev Twitter | **~€3.35/mo** class (2 vCPU / 2 GB) in comparison tables | Good price; check API/automation needs |
| **[Hetzner Cloud](https://www.hetzner.com/cloud)** | **Default** recommendation — not hidden, but **baseline** for value | **~€3.79/mo** (2 vCPU / 4 GB ARM or CX22) | Best perf/flex for developers; hourly billing |
| **[Scaleway](https://www.scaleway.com/en/)** | Stardust / legacy cheap instances | Occasional **€0.01** or very low tiers (capacity-limited) | Good EU option; read instance lifecycle docs |

**PrivateMind fit:** A **€2 IONOS or €4 Hetzner** box is often a better **dedicated server** than $0 Oracle if you need reliable `privatemind wake` + `worker serve` without “out of capacity.” Pair with **free** GitHub + Groq/Gemini for inference — total stack still **single-digit euros**.

**Hetzner vs IONOS (rule of thumb):** Hetzner wins **raw perf, hourly billing, terraform**; IONOS wins **lowest sticker price and bundled beginner extras** — compare **renewal**, not homepage hero price ([comparison example](https://eurohosting.org/compare/hetzner-vs-ionos)).

---

## Startup / trial credits (time-limited, often hidden in “Programs”)

Worth cataloguing when the agent researches; **not** $0 forever:

| Program | Rough credit | Catch |
|---------|--------------|--------|
| Google Cloud Free Trial | **$300 / 90 days** | Card usually required; must not exceed always-free accidentally |
| Google for Startups / pre-funded | **~$2k** tiers reported in indie guides ([example roundup](https://klymentiev.com/blog/free-cloud-credits-developers)) | Eligibility forms |
| AWS Activate Founders | **~$1k** | Application |
| Microsoft Founders Hub | **~$1k–5k** | Application |
| IONOS / UpCloud / Civo trials | **€200–500** for ~30 days ([summary](https://aifree.dev/compare/free-cloud-credits)) | One-time; card |

Record **expiry** in limitation ledger when an operator burns these for a migration spike.

---

## How to research hidden / cheap options

The agent (or operator) should treat this as **ongoing recon**, not a one-time README:

1. **Read vendor “Limits”, “Product usage included”, “Always Free Resources”** — not landing-page pricing alone (Kaggle GPU hours live in [efficient-gpu-usage](https://www.kaggle.com/docs/efficient-gpu-usage); GitHub Codespaces in [product usage included](https://docs.github.com/en/billing/reference/product-usage-included)).
2. **Check account settings UI** — quotas (Kaggle profile, Groq Limits page, Gemini AI Studio) override stale blog posts.
3. **Compare renewal vs intro** for VPS/hosting (IONOS, OVH, Namecheap-style promos).
4. **Search** `"floating quota"`, `"always free"`, `site:docs.*.com included` — then **verify** on official docs dated within the last year.
5. **Record** findings here: service, allowance, link, `verified_on` date, and whether it fits **brain**, **worker**, **batch**, or **LLM only**.
6. **Do not** store payment cards or bypass ToS in automation — propose operator signup steps in limitations if blocked.

When adding integrations, prefer **approved tools + sandbox** and document spend caps in `record_limitation`.

---

## Inference comparison (free-first)

| Provider | Billing | Rough free limits | Tradeoffs |
|----------|---------|-------------------|-----------|
| **Local Ollama** | $0 | Hardware-bound | Best privacy; you operate the model |
| **Groq** | $0 tier | Model-specific RPM/RPD/TPM ([docs](https://console.groq.com/docs/rate-limits)) | Fast; limits are org-wide |
| **NVIDIA NIM (hosted)** | $0 dev | Per-model RPM; [integrate.api.nvidia.com](https://integrate.api.nvidia.com/v1) | Strong catalog; production needs AI Enterprise |
| **Gemini API** | $0 tier | Model-specific; view in AI Studio | Strong models; free tier may use prompts for product improvement * |
| **OpenRouter `:free`** | $0 models | 50/day (20/min) default; 1000/day after $10 credits ([limits](https://openrouter.ai/docs/api/reference/limits)) | Aggregator; provider throttling at peaks |
| **Aion Labs** | $0 daily allowance | ~15 RPM, token/day cap ([limits](https://api.aionlabs.ai/docs/rate-limits/)) | OpenAI-compatible; no card for trial allowance |
| **Kilo Gateway `:free`** | $0 models | ~200 req/h/IP on free models ([docs](https://kilo.ai/docs/gateway/usage-and-billing)) | May route to NVIDIA trial — no confidential prompts |
| **LLM7.io** | Free token | Token/day caps vary ([limits](https://docs.llm7.io/limits)) | Community endpoint; quotas can shrink under load |
| **ModelScope API-Inference** | $0 for registered dev | Magicube / daily rules ([intro](https://www.modelscope.cn/docs/model-service/API-Inference/intro)) | Often needs Alibaba Cloud link; non-production |
| **SiliconFlow (free models)** | $0 | Fixed RPM/TPM per model ([docs](https://docs.siliconflow.com/en/userguide/rate-limits/rate-limit-and-upgradation)) | Strong CN-hosted open models |
| **OVH AI Endpoints** | Anonymous + key | 2 RPM/IP/model anonymous; 400 RPM with key ([caps](https://docs.ovhcloud.com/en/public-cloud/ai-machine-learning/ai-endpoints-capabilities/)) | EU sovereignty; OpenAI-compatible |
| **SambaNova Cloud** | Docs: free w/o payment method | Per-model RPM/RPD ([rate limits](https://docs.sambanova.ai/docs/en/models/rate-limits)) | Fast RDU inference; card/402 behavior — verify live |
| **UnoRouter** | `:free` models | ~1 req/min/model + upstream caps ([docs](https://unorouter.com/en/docs/platform/errors-and-rate-limits)) | Aggregator over ~50 free upstreams; rotate models on 429 |
| **Cohere / Mistral / Z.AI / HF / Ollama Cloud** | Varies | Check console | Catalog + `seed-catalog`; probe before relying |
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
