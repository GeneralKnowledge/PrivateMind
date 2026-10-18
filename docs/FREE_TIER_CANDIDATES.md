# Free-tier candidates (backlog)

Living backlog of **under-advertised** services to probe and judge. The agent updates this file and/or logs rows via `privatemind research candidate`. **Verdicts** in the CLI/memory are authoritative for what was actually tested.

| Slug | Category | Why it’s hidden | Initial verdict |
|------|----------|-----------------|-----------------|
| `nvidia-nim-hosted` | llm | “Free inference” on [build.nvidia.com](https://build.nvidia.com/) — RPM limits per model, not a credit balance | **useful** for prototyping — wire as OpenAI-compatible LLM |
| `nvidia-nim-self-hosted` | gpu | Downloadable NIM containers (NGC); free dev/test on up to 16 GPUs ([Run NIM Anywhere](https://docs.api.nvidia.com/nim/docs/run-anywhere)) | pending — needs GPU host |
| `google-codelab-credits` | gpu/batch | No-card credits via [codelab credits](https://codelabs.developers.google.com/codelabs/cloud-codelab-credits) | pending — batch GCP only |
| `paperspace-gradient-free` | gpu/batch | Free Gradient GPU tier; long session auto-stop | pending — spillover GPU |
| `kaggle-gpu-weekly` | gpu/batch | ~30 GPU h/week in UI/docs | pending — notebook workflow |
| `modal-starter-30` | gpu/batch | [$30/mo included compute](https://modal.com/pricing) on Starter | pending — serverless burst |
| `nvidia-launchpad` | gpu/batch | Browser access to enterprise HW ([deployment FAQ](https://docs.api.nvidia.com/nim/docs/deployment)) | pending |
| `hf-serverless-nim` | llm | Selected NIM on Hugging Face serverless | pending |
| `replicate-free-runs` | gpu/batch | Limited free inference runs | pending |
| `e2b-dev` | sandbox | Dev sandbox credits (check current site) | pending |
| `lightning-ai` | gpu/batch | Free GPU hours promos (varies) | pending |

See [FREE_TIER_RESEARCH.md](FREE_TIER_RESEARCH.md) for methodology and tiering.
