# Web search & grounding (October 2026)

PrivateMind’s agent should think **beyond LLM routers**: recon, fact-checking, and tool planning often need **search results** or **instant answers**, not another chat completion.

**Machine-readable:** [`data/free_tier_tool_entitlements.json`](data/free_tier_tool_entitlements.json)  
**CLI:** `privatemind research tool-entitlements [--class A|B|C]` · `privatemind research probe-brave-search`

---

## Two different needs

| Need | Typical API | PrivateMind pattern |
|------|-------------|---------------------|
| **SERP** — URLs, snippets, ranks for the agent to read | Brave Search (web), OpenSERP, Tavily | Approved tool → sandbox → memory (unverified until cross-check) |
| **Instant answer** — one grounded blob + citations | Brave **Answers** plan | Short planner step; log sources in task context |
| **Free knowledge** — stable facts | Wikipedia REST | Low rate; great for definitions |
| **Self-hosted SERP** — no vendor key | OpenSERP on worker | Body server; respect search engine ToS |

Do **not** route search through GitHub. Keys live in the **vault**; calls go through **approved tools** only.

---

## Brave (operator highlight)

Brave is the best-documented **commercial** option that still fits small agents:

- **Search plan** — `$5/month` renewable credit ≈ **~1,000 web searches**; includes **LLM Context** endpoint for RAG-style grounding ([pricing](https://brave.com/search/api/)).
- **Answers plan** — **instant answers** with citations; priced per answer + tokens ([blog](https://brave.com/blog/most-powerful-search-api-for-ai/)).
- **Card** required for signup; set dashboard **spend cap = free credits** to avoid surprise bills ([FAQ](https://api-dashboard.search.brave.com/documentation/resources/help-feedback)).
- **Class B** in our catalogue (monthly allowance, not unlimited permanent free).

Probe after adding `BRAVE_SEARCH_API_KEY` to the vault:

```bash
privatemind research probe-brave-search
```

---

## SERP without a big vendor bill

| Option | Class | Notes |
|--------|-------|-------|
| **OpenSERP** (self-host) | A | MIT; Google/Bing/DDG/etc. on localhost — ToS/robots risk is yours |
| **FreeSerp** (hosted keyless) | C | Probe ToS before agents hammer it |
| **Google CSE JSON** | B legacy | No new customers; sunset 2027 |

---

## Agent workflow (out-of-the-box thinking)

1. **Ask** — “What capability is missing?” (e.g. live web, not another LLM).
2. **Discover** — read tool entitlements + run probes; add rows with official URLs.
3. **Wrap** — `tool-request approve` with sandbox runner (never embed keys in core).
4. **Verify** — compare answer to a second source; promote memory only with evidence.
5. **Record** — `privatemind research candidate --category search` with verdict.

See [IDEAS_FOR_THE_AGENT.md](IDEAS_FOR_THE_AGENT.md) — **Capabilities beyond inference**.

---

## UK developer

Brave/Tavily/Exa are US/global SaaS — standard GDPR contractual terms apply. **OpenSERP** scraping may hit regional CAPTCHAs; prefer official APIs for production recon. Wikipedia is fine with descriptive User-Agent.
