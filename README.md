# Jonathan Gomez Aguilar

**Backend & AI Infrastructure Engineer**
Building systems where AI behavior is predictable, costs are controlled, and data models don't lie.

I design and ship backend infrastructure with a focus on reliability and correctness — AI routing systems that control inference cost, agent harnesses that make model behavior auditable, and financial tools built on integer arithmetic instead of floating-point optimism. My projects reflect a consistent preference for systems that fail loudly, log honestly, and are designed to limit hidden technical debt — a design direction I keep revisiting, not a guarantee.

Beyond that core, I build in public across mobile and games: an on-device Android LLM host, a Game Boy Advance emulator core, and a few strategy and RPG prototypes. The through-line is the same — a preference for deterministic behavior, explicit boundaries, and claims you can verify against the linked repositories instead of take on faith. Where a claim below is not verifiable from public source, it is labeled as such.

How I make and check claims: [docs/how-i-build.md](docs/how-i-build.md) · Project index with licenses: [docs/project-index.md](docs/project-index.md)

---

## Featured Projects

**[Babel](https://github.com/gthgomez/Babel)** *(Apache-2.0)* — An open-source agent harness for real software work: a local coding agent with a conversational **chat** loop, explicit **plan** and **deep** modes, and an inspectable Prompt OS composed from a versioned instruction catalog. Around the model sits a deterministic control surface — approval gates, mode policies, Docker isolation profiles, revision-bound evidence receipts, and a completion gate that verifies work against a specific repository revision instead of trusting the model's say-so.

- *Demonstrated:* modes and catalog composition in `babel-cli/src/interactive/`; revision-bound receipts in `babel-cli/src/evidence/`; regression-gate suites tracked in `REGRESSION_LEDGER.md`; a tag-gated release workflow that builds a bundle in CI for manual owner review and publication ([latest release](https://github.com/gthgomez/Babel/releases/latest)).
- *Limitation:* end-to-end output reproducibility is a design goal, not a tested guarantee — provider-side model output is treated as non-reproducible. The governed request path is heavier than a bare model call.

**[Prismatix](https://github.com/gthgomez/Prismatix)** *(MIT)* — A cost-aware multi-provider AI chat client. Each request is classified into a routing role and mapped to a curated, priced model through the OpenCode model hub, and the UI explains every choice. Cost safety is fail-closed: an unknown or expired price rejects the request rather than silently re-routing to something more expensive, and when a provider is unavailable, fallback candidates more expensive than the decided model are skipped. One normalized SSE stream spans every gateway; direct Anthropic/OpenAI/Gemini/NVIDIA/DeepInfra routes remain as an explicit legacy fallback, not the default path. Live app: <https://prismatix-app.vercel.app>.

- *Demonstrated:* fail-closed pricing in `supabase/functions/router/pricing_registry.ts`; cheaper-only provider fallback in `supabase/functions/router/provider_availability.ts`; per-answer routing disclosure (`X-Route-Decision`, cost-estimate headers); SSE normalization in `supabase/functions/router/sse_normalizer.ts`.
- *Limitation:* the complexity score is keyword/regex heuristics with tuned thresholds — it needs ongoing calibration, and adds latency on the scoring step.

**[MonteCarlo-Ledger](https://github.com/gthgomez/MonteCarlo-Ledger)** *(MIT)* — A local-first finance CLI and API with a ledger-first SQLite core that stores monetary values as integer cents — no floating-point arithmetic at the data layer — and projects income and expenses over a configurable horizon (default 90 days) using seeded Monte Carlo simulations (default 500 runs) with a configurable quantile, so risk comes from a distribution, not an average. The companion [Android app](https://github.com/gthgomez/MonteCarloLedger-Android) adds bill pacing and AES-GCM encrypted backups (encrypted backups, not an encrypted live database) with no network permission.

- *Demonstrated:* integer-cents schema in `monte_carlo_ledger/schema.sql`; integer-safety tests in `tests/test_int_safety.py`; seeded `SplitMix64` PRNG in `monte_carlo_ledger/contract/prng.py`; safe-to-spend computed from the Monte Carlo minimums distribution at the configured quantile (`monte_carlo_ledger/contract/engine.py`, decision MCD-0008).
- *Limitation:* the simulation core never reads a clock — `as_of` is always an explicit input — but the HTTP layer defaults `as_of` to today, so API runs are date-dependent when the caller omits it (see the repo's determinism notes). No multi-currency support, by design.

**[Scout](https://github.com/gthgomez/Scout)** *(MIT)* — A local CLI that finds paid open-source bounty candidates and packages each one into artifacts a coding agent can pick up and execute — Cursor, Claude Code, Codex, Gemini, or anything else able to follow a runbook. Policy gates are enforced against Scout's own operations (pre-execution checks against an egress allowlist, not runtime packet filtering); discovery reads public GitHub/Algora APIs, and the bounty work itself runs locally.

- *Demonstrated:* shipped [v0.6.2 release](https://github.com/gthgomez/Scout/releases/tag/v0.6.2), CI, `CONTRIBUTING.md`, `CHANGELOG.md`, `.editorconfig`, a Dockerfile, and architecture docs under [`docs/architecture/`](https://github.com/gthgomez/Scout/tree/main/docs/architecture); policy enforcement in `src/scout/policy.js`.
- *Limitation:* Scout's own honesty note in `src/scout/network-design.js` says it does not enforce packet-level egress filtering or observe runtime traffic.

---

## More Projects

**[PrismLocal](https://github.com/gthgomez/PrismLocal)** — Android app for private, on-device GGUF LLM inference. Embeds a C++20 `llama.cpp` runtime behind a thread-safe JNI bridge, with chat, tool dispatch, and local document retrieval (RAG). Inference is on-device; the app itself can use an optional cloud endpoint. *(Apache-2.0)*

**[GBA_Emulator](https://github.com/gthgomez/GBA_Emulator)** — Portable Game Boy Advance emulator core (C++17), validated against 13 public mGBA test suites — 11 green, 2 not full (`misc-edge`, `timing`) — with a committed green-suite baseline and credibility-matrix tooling. Physical-device soak runs have recorded audio/pacing failures; device qualification is tracked openly in the repo. *(Apache-2.0)*

**[GbaEmulatorAndroid](https://github.com/gthgomez/GbaEmulatorAndroid)** — Android development shell for the GBA_Emulator core: Compose UI, SAF ROM loading, a SurfaceView 240x160 viewport, Oboe audio, and a JNI/CMake bridge into the sibling C++ core. *(Apache-2.0)*

**[MonteCarloLedger-Android](https://github.com/gthgomez/MonteCarloLedger-Android)** — Kotlin/Compose financial ledger app focused on deterministic forecasting, bill pacing, and AES-GCM encrypted backups. Manifest declares no internet permission. *(Public source, all rights reserved)*

**[ProofPath](https://github.com/gthgomez/ProofPath)** — Offline-first React Native learning system that turns lessons into reviewer-ready portfolio evidence, built around active engineering exercises instead of passive content. *(Public source, all rights reserved)*

**[DragonWake](https://github.com/gthgomez/DragonWake)** — Multiplayer web MMORTS prototype in active development: async city builder plus map combat, with a server-derived Dragon Presence lifecycle and canonical save migration. Status (prototype alpha, campaign and branch qualification) is tracked in the repo README; real database and device claims require separate receipts there. *(Public source, all rights reserved)*

**[Orbitscar](https://github.com/gthgomez/Orbitscar)** — Clean-room sci-fi strategy prototype: a deterministic headless battle/colony simulation package, declarative content validation, and an accessible DOM command surface beside a Phaser tactical view. *(Public source, all rights reserved)*

**[ManaNet](https://github.com/gthgomez/ManaNet)** — Cyber-themed tower defense game and a Godot 4.6 / GDScript port of the Python/Kivy TowerDefenseKivy. *(Public source, all rights reserved)*

**[GravityPivot](https://github.com/gthgomez/GravityPivot)** — Hyper-casual physics space-navigation game: tether to gravity anchors to orbit, swing, and sling through an infinite cave. Refactored out of a single-file prototype into engine/renderer/audio/ui modules on TypeScript + Vite, with Vitest coverage. *(Public source, all rights reserved)*

**[reliquary](https://github.com/gthgomez/reliquary)** — Medieval-fantasy monster-binding RPG prototype: elemental battles, creature evolution, binding, party and box storage, saves, and keyboard/touch controls. *(Public source, all rights reserved)*

**[WallpaperCropFixer](https://github.com/gthgomez/WallpaperCropFixer)** — On-device Android utility that positions crops around faces with ML Kit and handles EXIF orientation correctly. Photo processing is on-device; the app-owned permission is `SET_WALLPAPER`, but the merged manifest also carries `INTERNET`/`ACCESS_NETWORK_STATE` from the ML Kit SDK's telemetry transport — disclosed in the repo's [PRIVACY.md](https://github.com/gthgomez/WallpaperCropFixer/blob/main/PRIVACY.md). Store/privacy readiness is not yet certified. *(Public source, all rights reserved)*

**[ExactUploadFixer](https://github.com/gthgomez/ExactUploadFixer)** — Android (Kotlin/Compose) utility that resizes and compresses images to meet exact upload requirements — dimensions and file size — for things like passport or visa-photo submissions. Free manual tier plus Pro presets via Play Billing, with an Amazon flavor. *(Public source, all rights reserved)*

**[babel-origin-site](https://github.com/gthgomez/babel-origin-site)** — Public static origin and bounded demo front door for Babel. *(Public source, all rights reserved)*

---

## Private & Commercial

Not everything here has a public repository. These projects are real and shipped, but the source is not published — the only thing to inspect is the live product. Treat the entries below as non-public case studies: claims about them cannot be verified from public source, so they carry no public evidence status.

**[GPCGuard](https://www.gpcguard.app)** *(private repository — source not published; non-public case study)*
Privacy compliance is a legal requirement, but most engineering teams have no systematic way to verify it. GPCGuard is a GPC/CCPA compliance SaaS that detects and reports on Global Privacy Control opt-out signals as required under CCPA/CPRA, CPA, CTDPA, and NJDPA. It includes a Python scanner suite, Stripe billing, a Next.js dashboard, and Supabase Edge Functions on the backend. Live at [gpcguard.app](https://www.gpcguard.app). A security audit was performed privately; neither the audit nor the source is publicly inspectable, so no public qualification is claimed here.

---

## How to Verify

These projects are designed to be inspectable, not just described. Entry points:

- **GPCGuard** — live product: <https://www.gpcguard.app> (private repo — product surface only, no public source)
- **Prismatix** — live app: <https://prismatix-app.vercel.app> · [routing and cost behavior](https://github.com/gthgomez/Prismatix#auto-routing--cost-safety--what-actually-happens) documented in the repo README
- **Babel** — [latest release](https://github.com/gthgomez/Babel/releases/latest); the release workflow builds tag bundles in CI and the owner publishes the reviewed draft
- **Scout** — [v0.6.2 release](https://github.com/gthgomez/Scout/releases/tag/v0.6.2), CI, `CONTRIBUTING.md`, and architecture docs
- **GBA_Emulator** — committed [green-suite baseline](https://github.com/gthgomez/GBA_Emulator); build/regression, accuracy, and device qualification are tracked separately, and not all suites are green
- **Babel origin site** — <https://babel-origin-site.vercel.app>

For the code behind the headline claims, each featured project above names the files that implement its cost-safety, gating, correctness, and evidence behavior.

---

## Design Principles

Shared properties I actively design toward — aspirations I hold projects to, not claimed properties of every file:

**Determinism over convenience** — same input, same output; variability is controlled and observable.
**Fail-fast over silent degradation** — invalid states are blocked and surfaced with explicit reasoning.
**Cost as a first-class constraint** — routing, budgets, and simulation design account for resource usage from the start.
**Correctness at the lowest level** — integer money storage, catalog-backed instruction plans, priced routing registries.

---

## Key Tradeoffs

**Prismatix: runtime routing over static config; safety over availability.** Role-based scoring at request time adapts to prompt length and mixed intent, at the cost of a scoring step that needs tuning. Fail-closed cost safety means occasional hard failures when a price is unknown — chosen over silent fallback to costlier providers.

**Babel: a governed agent loop over a bare model call.** Validated, catalog-backed instruction plans and explicit gates make behavior auditable, at the cost of a heavier request path and more moving parts. Provider-side outputs are not reproducible, and the harness does not claim otherwise.

**MonteCarlo-Ledger: integer cents over decimal types.** `DECIMAL` rounding is database-specific and `float` accumulates error; integer cents make every conversion explicit at the input/display layers. Multi-currency support was intentionally not built — doing it correctly requires exchange-rate versioning tied to transaction timestamps, and doing it naively would corrupt historical projections.

---

## What I Would Improve in Production

- Add full request/response tracing dashboards for Prismatix (latency and cost per route, per provider)
- Introduce persistent execution logs and replay tooling for Babel to support post-hoc debugging
- End-to-end reproducibility tests for Babel's pipeline, so reproducibility is a tested property rather than a goal
- Replace the remaining emulator interactive oracles with deterministic frame-hash coverage as the GBA core matures

---

## Where to Start

| Repo | What it demonstrates |
|---|---|
| **[Babel](https://github.com/gthgomez/Babel)** | Systems design — governance, contracts, auditability |
| **[Scout](https://github.com/gthgomez/Scout)** | OSS project hygiene — policy enforcement, agent handoff, CI, docs, releases |
| **[Prismatix](https://github.com/gthgomez/Prismatix)** | Production tradeoff reasoning — cost, latency, provider abstraction |
| **[GPCGuard](https://www.gpcguard.app)** | End-to-end product delivery — compliance domain, full-stack, shipped (non-public case study; private repo, no public source or receipts) |
| **[PrismLocal](https://github.com/gthgomez/PrismLocal)** | Systems + mobile — native runtime integration (JNI/C++), privacy |
| **[MonteCarlo-Ledger](https://github.com/gthgomez/MonteCarlo-Ledger)** | Data correctness — determinism, integer money, clean schema |
| **[GBA_Emulator](https://github.com/gthgomez/GBA_Emulator)** | Low-level rigor — test-oracle evidence, emulation correctness |
| **[DragonWake](https://github.com/gthgomez/DragonWake)** / **[Orbitscar](https://github.com/gthgomez/Orbitscar)** | Game systems — simulation, multiplayer, deterministic state |

---

## Stack

TypeScript · Python · Kotlin · C++17 · React · Next.js · React Native · Deno · Supabase · SQLite · Android (Jetpack Compose) · Godot (GDScript) · Phaser

---

## Currently Focused On

Backend systems, AI infrastructure, and applied ML tooling — currently agent harnesses, cost-aware routing, and on-device inference. Open to internship and early-career roles in software engineering, ML infrastructure, or backend development.

[LinkedIn](https://linkedin.com/in/gthgomez)

## License

This profile repository is publicly viewable for portfolio and project-navigation purposes. It is not open source. See [LICENSE](LICENSE) for permitted use. Referenced projects and third-party materials retain their own licenses.
