# Jonathan Gomez Aguilar

**Backend & AI Infrastructure Engineer**
Building systems where AI behavior is predictable, costs are controlled, and data models don't lie.

I design and ship backend infrastructure with a focus on reliability and correctness — AI routing systems that control inference cost, agent harnesses that make model behavior auditable, and financial tools built on integer arithmetic instead of floating-point optimism. My projects reflect a consistent preference for systems that fail loudly, log honestly, and scale without accumulating hidden technical debt.

Beyond that core, I build in public across mobile and games: an on-device Android LLM host, a Game Boy Advance emulator core, and a few strategy and RPG prototypes. The through-line is the same — deterministic behavior, explicit boundaries, and claims you can verify instead of take on faith.

---

## Featured Projects

**[GPCGuard](https://www.gpcguard.app)** *(public release in progress)*
Privacy compliance is a legal requirement, but most engineering teams have no systematic way to verify it. GPCGuard is a GPC/CCPA compliance SaaS that detects and reports on Global Privacy Control opt-out signals as required under CCPA/CPRA, CPA, CTDPA, and NJDPA. It includes a Python scanner suite, Stripe billing, a Next.js dashboard, and Supabase Edge Functions on the backend. Security audit complete; live at [gpcguard.app](https://www.gpcguard.app).

**[Babel](https://github.com/gthgomez/Babel)**
AI systems fail in production not because the model is wrong, but because agent behavior is inconsistent, unversioned, and impossible to audit. Babel is an open-source agent harness for real software work: a local coding agent with a conversational **chat** loop, explicit **plan** and **deep** modes, and an inspectable Prompt OS underneath. Around the model it composes a deterministic control surface — controller gates, mode policies, isolation profiles, revision-bound verification, completion authority, and hash-linked evidence — so the operating instructions stay visible and testable. The independent [Babel vs. ZCode harness deep-dive](https://github.com/gthgomez/babel-vs-zcode-harness-report) compares it against another harness dimension by dimension.

**[Prismatix](https://github.com/gthgomez/Prismatix)**
Running every prompt through the most capable model is expensive and slow. Prismatix is a cost-aware multi-provider AI chat client: each request is classified into a routing role and mapped to a curated, priced model through the OpenCode model hub, and the UI explains every choice. Cost safety is fail-closed — if a price is unknown, the request is rejected rather than silently re-routed to something more expensive. One normalized SSE stream spans every gateway and protocol. Direct Anthropic/OpenAI/Gemini/NVIDIA/DeepInfra routes remain as an explicit legacy fallback, not the default path.

**[MonteCarlo-Ledger](https://github.com/gthgomez/MonteCarlo-Ledger)**
Personal finance software that rounds incorrectly or simulates with too few runs gives you false confidence in your projections. MonteCarlo-Ledger is a local-first finance CLI and API with a ledger-first SQLite core that stores monetary values as integer cents — eliminating floating-point rounding errors at the data layer — and runs bounded Monte Carlo simulations to produce safe-to-spend projections grounded in variance, not averages. The companion [Android app](https://github.com/gthgomez/MonteCarloLedger-Android) adds deterministic bill pacing and AES-GCM encrypted backups.

---

## More Projects

**[PrismLocal](https://github.com/gthgomez/PrismLocal)** — Apache-2.0 Android app for private, on-device GGUF LLM inference. Embeds a C++20 `llama.cpp` runtime behind a thread-safe JNI bridge, with chat, tool dispatch, and local document retrieval (RAG).

**[GBA_Emulator](https://github.com/gthgomez/GBA_Emulator)** — Portable Game Boy Advance emulator core (C++17), validated against 13 public mGBA test suites with a committed regression baseline and a credibility matrix, plus a sibling Android dev shell.

**[MonteCarloLedger-Android](https://github.com/gthgomez/MonteCarloLedger-Android)** — Kotlin/Compose financial ledger app focused on deterministic forecasting, bill pacing, and encrypted backups. No network dependency.

**[ProofPath](https://github.com/gthgomez/ProofPath)** — Offline-first React Native learning system that turns lessons into reviewer-ready portfolio evidence, built around active engineering exercises instead of passive content.

**[DragonWake](https://github.com/gthgomez/DragonWake)** — Multiplayer web MMORTS MVP beta: async city builder plus map combat, with a server-derived Dragon Presence lifecycle and canonical save migration.

**[Orbitscar](https://github.com/gthgomez/Orbitscar)** — Clean-room sci-fi strategy prototype: a deterministic headless battle/colony simulation in one package, declarative content validation in another, and an accessible DOM command surface beside a Phaser tactical view.

**[reliquary](https://github.com/gthgomez/reliquary)** — Medieval-fantasy monster-binding RPG prototype: elemental battles, creature evolution, binding, party and box storage, saves, and keyboard/touch controls. Public source, all rights reserved.

**[WallpaperCropFixer](https://github.com/gthgomez/WallpaperCropFixer)** — On-device Android utility that positions crops around faces with ML Kit and handles EXIF orientation correctly. Requests only `SET_WALLPAPER`; photos never leave the device.

**[babel-vs-zcode-harness-report](https://github.com/gthgomez/babel-vs-zcode-harness-report)** — Ten fact-checked dimensions comparing two agent harnesses, with simulations and verdicts. A template for evaluating harness design instead of trusting vibes.

**[babel-origin-site](https://github.com/gthgomez/babel-origin-site)** — Public static origin and bounded demo front door for Babel.

---

## Proof of Work

These projects are designed to be verifiable, not just described. Start with the live surfaces:

- **GPCGuard** — live product: <https://www.gpcguard.app>
- **Prismatix** — live app: <https://prismatix-app.vercel.app> · routing and cost behavior documented in the [repo README](https://github.com/gthgomez/Prismatix#auto-routing--cost-safety--what-actually-happens)
- **Babel** — [latest release](https://github.com/gthgomez/Babel/releases/latest), a public release gate in CI, and an independent [harness comparison report](https://github.com/gthgomez/babel-vs-zcode-harness-report)
- **GBA_Emulator** — green mGBA suites plus a committed [credibility matrix baseline](https://github.com/gthgomez/GBA_Emulator)
- **Babel origin site** — <https://babel-origin-site.vercel.app>

Then read how each behaves under the hood.

### Prismatix — model routing in practice

**What actually happens:**

- A simple query (e.g. "summarize this text") is routed to an `economy`/`fast` role backed by a low-cost model
- A complex task (e.g. code generation or multi-step reasoning) is routed to a `strong`/`max` role
- Every Auto-routed answer exposes the chosen role, model, gateway, reason, whether a fallback was used, and the estimated cost basis
- An unknown price fails the request closed rather than quietly spending more; provider fallback may only re-route to a *cheaper* priced model
- All responses stream through a single normalized SSE interface regardless of which provider handles the request

**What to look for in the code:**

- Role-based routing decisions with deterministic in-role fallbacks
- No provider-specific branching in client-facing code
- Consistent streaming output regardless of backend model
- Cost safety enforced server-side (`supabase/functions/router/pricing_registry.ts`)

### Babel — deterministic agent execution

**What actually happens:**

- The selected Prompt OS stack is previewable before any model acts
- The stack is composed into a validated, catalog-backed instruction plan before execution begins
- Governance layers decide what a mode may do: controller gates, isolation profiles, and mode policies
- Completion is verified against a specific repository revision rather than asserted by the model
- If the plan is incomplete, underspecified, or violates interface contracts, execution is blocked with an explicit failure state — not silently degraded

**What to look for in the code:**

- Preview → Compose → Validate → Execute flow on every run
- No direct model execution without a validated instruction plan
- Regression and release-gate tests that catch behavioral drift before it ships
- Reproducible outputs given identical inputs and catalog state

### MonteCarlo-Ledger — correctness over convenience

**What actually happens:**

- All monetary values are stored as integer cents — no floating-point arithmetic at the data layer
- Income and expenses are projected forward across a 90-day horizon
- Bounded Monte Carlo simulations stress-test each projection
- The system outputs a safe-to-spend value derived from the worst-case distribution, not simple averages

**What to look for in the code:**

- Integer-only money storage throughout — no `float` for currency values
- Deterministic simulation seeding — identical inputs produce identical projections
- Clear separation between raw ledger data and derived projection output
- Ledger-first accounting: balances are derived, never treated as an editable source of truth

---

## Design Decisions

These projects share a set of properties that I actively design toward:

**Determinism over convenience**
Same input should produce the same output. Variability is controlled and observable, not accidental.

**Fail-fast over silent degradation**
Invalid states are blocked and surfaced with explicit reasoning. "Best effort" results that hide errors are worse than hard failures.

**Cost as a first-class constraint**
Routing decisions, budget enforcement, and simulation design are all built with resource usage in mind — not added as an afterthought.

**Correctness enforced at the lowest level**
Integer money storage, catalog-backed instruction plans, priced routing registries. Correctness bugs at the data layer propagate everywhere; fix them at the source.

---

## Key Tradeoffs

Specific decisions made across these projects — what I chose, what I ruled out, and where the current design has limits.

**Prismatix: runtime routing over static configuration, safety over availability**
Routing could have been a config file — map task types to models at deploy time. I built role-based scoring at request time instead because static config can't adapt to prompt length, context depth, or mixed-intent queries. The tradeoff is added latency on the scoring step and a complexity score that needs tuning. The harder call was fail-closed cost safety: when a model's price is unknown, or discovery returns no usable priced model for a role, the request fails with a readable error instead of silently falling back to a costlier provider. That means occasional hard failures, but no silent cost surprises. Provider fallback is deliberately constrained to cheaper priced models; broad automatic failover without proper logging first would make failures harder to diagnose, not easier.

**Babel: a governed agent loop over a bare model call**
The simplest agent is a model with tools and a loop. Babel composes a validated, catalog-backed instruction plan and wraps execution in explicit gates because unaudited behavior is invisible until it reaches production. The tradeoff is a heavier request path and more moving parts. Where it breaks: the catalog resolver assumes instruction entries are stable between deployments — hot-swapping catalog entries mid-session is not currently safe.

**MonteCarlo-Ledger: integer cents over decimal types**
Most finance software uses `DECIMAL` or `float` for readability. I use integer cents because rounding behavior in `DECIMAL` arithmetic is database-specific and `float` accumulates error across summation. The tradeoff is that every input and display layer must convert explicitly — there's no implicit formatting. What I intentionally did not build: multi-currency support. Adding it correctly requires exchange-rate versioning tied to transaction timestamps, which is a separate system; adding it naively would corrupt historical projections.

---

## What I Would Improve in Production

- Add full request/response tracing dashboards for Prismatix (latency and cost per route, per provider)
- Introduce persistent execution logs and replay tooling for Babel to support post-hoc debugging
- Expand MonteCarlo-Ledger with real-time ingestion and user-configurable scenario parameters
- Replace the remaining emulator interactive oracles with deterministic frame-hash coverage as the GBA core matures

---

## Where to Start

| Repo | What it demonstrates |
|---|---|
| **[Babel](https://github.com/gthgomez/Babel)** | Systems design — governance, contracts, auditability |
| **[Prismatix](https://github.com/gthgomez/Prismatix)** | Production tradeoff reasoning — cost, latency, provider abstraction |
| **[GPCGuard](https://www.gpcguard.app)** | End-to-end product delivery — compliance domain, full-stack, shipped |
| **[PrismLocal](https://github.com/gthgomez/PrismLocal)** | Systems + mobile — native runtime integration (JNI/C++), privacy |
| **[MonteCarlo-Ledger](https://github.com/gthgomez/MonteCarlo-Ledger)** | Data correctness — determinism, integer money, clean schema |
| **[GBA_Emulator](https://github.com/gthgomez/GBA_Emulator)** | Low-level rigor — test-oracle evidence, emulation correctness |
| **[DragonWake](https://github.com/gthgomez/DragonWake)** / **[Orbitscar](https://github.com/gthgomez/Orbitscar)** | Game systems — simulation, multiplayer, deterministic state |

Babel and Prismatix are the most architecturally complex. GPCGuard is the most complete product. PrismLocal and GBA_Emulator show the systems-native side. MonteCarlo-Ledger is smaller but demonstrates a data-correctness mindset that shows up consistently across all of the work.

---

## Stack

TypeScript · Python · Kotlin · C++17 · React · Next.js · React Native · Deno · Supabase · SQLite · Android (Jetpack Compose) · Godot (GDScript) · Phaser

---

## Currently Focused On

Backend systems, AI infrastructure, and applied ML tooling — currently agent harnesses, cost-aware routing, and on-device inference. Open to internship and early-career roles in software engineering, ML infrastructure, or backend development.

[LinkedIn](https://linkedin.com/in/gthgomez)

## License

This profile repository is publicly viewable for portfolio and project-navigation purposes. It is not open source. See [LICENSE.md](LICENSE.md) for permitted use. Referenced projects and third-party materials retain their own licenses.
