# Graduated autonomy

PrivateMind is designed to **stop micromanaging** once the trusted core and operator floor are in place.

## Operator floor (fixed)

The human (or host policy) sets immovable boundaries:

- Encrypted **vault** and SSH-first git identity.
- **Protected paths** the self-improvement loop cannot silently rewrite.
- **Worker verification** and quarantine — authenticity is not correctness.
- **No automatic merge to `main`** — promotion stays a human decision.

These are not goals for the agent to “optimize away”; they are the definition of the trusted core.

## Agent latitude (above the floor)

Everything else is fair game for the agent’s own improvement loop: tooling, docs, schedulers, verifiers, UX, tests, worker job types, sandbox hardening on the body server, **web search / grounding tools** ([WEB_SEARCH_AND_TOOLS_OCT2026.md](WEB_SEARCH_AND_TOOLS_OCT2026.md)), and items in [IDEAS_FOR_THE_AGENT.md](IDEAS_FOR_THE_AGENT.md).

The executive should:

1. **Pursue capability domains** proactively ([AGENT_CAPABILITY_MANDATE.md](AGENT_CAPABILITY_MANDATE.md)): inference, search, **email**, **SMS/phone**, **crypto**, **fiat (later)** — discover free tiers, then request vault entries; never self-open bank accounts or use the operator’s personal inbox.
2. Propose changes on branches with evidence (tests, limitations when blocked).
3. Store uncertain claims as **unverified** memory until promoted.
4. Ask for human help when touching protected surfaces or when verification fails.

## For operators

You do not need to implement the full roadmap upfront. Seed accounts, wake the agent, point it at the repo, and optionally skim `IDEAS_FOR_THE_AGENT.md` and `FREE_TIER_RESEARCH.md`. After the floor is stable, **outcomes depend on what the agent prioritizes**, not on a central feature checklist.
