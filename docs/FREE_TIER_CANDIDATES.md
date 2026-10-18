# Free-tier candidates (backlog)

Living backlog of **under-advertised** services to probe and judge. The agent updates this file and/or logs rows via `privatemind research candidate`. **Verdicts** in the CLI/memory are authoritative for what was actually tested.

**LLM router catalog:** Provider keys in [data/free_tier_provider_catalog.json](data/free_tier_provider_catalog.json) align with multi-provider quota JSON (`schema_version` `2026-09-27`). Run `privatemind research seed-catalog` to copy them into memory as `pending`.

## LLM / inference (quota-router providers)

| Slug | Category | Why it’s hidden | Initial verdict |
|------|----------|-----------------|-----------------|
| `aion-labs` | llm | Daily credit allowance, not headline “free API” ([pricing](https://api.aionlabs.ai/pricing/)) | pending |
| `cohere-trial` | llm | Trial keys vs production | pending |
| `google-gemini` | llm | Limits live in AI Studio, not one table | pending |
| `mistral-api` | llm | Console-dependent allowances | pending |
| `z-ai-glm` | llm | Often via Kilo `:free` / BYOK | pending |
| `cloudflare-workers-ai` | llm | Neurons/day buried in Workers pricing | pending |
| `groq` | llm | Well known but still worth probing limits | pending |
| `huggingface-inference` | llm | Credits + serverless NIM subset | pending |
| `kilo-gateway-free` | llm | `:free` models + IP rate limits | pending |
| `llm7-io` | llm | Community OpenAI endpoint | pending |
| `modelscope-inference` | llm | Magicube quotas vs old “2000/day” blogs | pending |
| `nvidia-nim-hosted` | llm | RPM per model on build.nvidia.com | **useful** for prototyping |
| `ollama-cloud` | llm | Cloud slice changes often | pending |
| `openrouter-free` | llm | `:free` suffix models | pending |
| `ovhcloud-ai-endpoints` | llm | **Anonymous** 2 RPM/IP — easy to miss | pending |
| `siliconflow-free` | llm | Free model names without `Pro/` prefix | pending |
| `sambanova-cloud` | llm | Listed on GitHub free-API repos; card rules disputed | pending — operator reports still working |
| `unorouter-free` | llm | 130+ `:free` models; easy to miss vs direct upstream keys | pending — good spillover aggregator |

**GitHub list recon:** `privatemind research github-sync` — see [FREE_TIER_RESEARCH.md](FREE_TIER_RESEARCH.md#github-as-the-living-source-of-lists).

## GPU / batch / host (non-router)

| Slug | Category | Why it’s hidden | Initial verdict |
|------|----------|-----------------|-----------------|
| `nvidia-nim-self-hosted` | gpu | NGC containers; free dev on up to 16 GPUs | pending — needs GPU host |
| `google-codelab-credits` | gpu/batch | No-card codelab credits | pending — batch GCP only |
| `paperspace-gradient-free` | gpu/batch | Free Gradient tier; auto-stop | pending — spillover GPU |
| `kaggle-gpu-weekly` | gpu/batch | ~30 GPU h/week in UI/docs | pending — notebook workflow |
| `modal-starter-30` | gpu/batch | $30/mo included compute on Starter | pending |
| `nvidia-launchpad` | gpu/batch | Browser enterprise HW trials | pending |
| `hf-serverless-nim` | llm | Selected NIM on Hugging Face serverless | pending |
| `replicate-free-runs` | gpu/batch | Limited free inference runs | pending |
| `e2b-dev` | sandbox | Dev sandbox credits | pending |
| `lightning-ai` | gpu/batch | Free GPU hour promos (varies) | pending |

See [FREE_TIER_RESEARCH.md](FREE_TIER_RESEARCH.md) for methodology and tiering.
