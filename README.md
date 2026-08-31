# Jonathan Gomez Aguilar

**Backend & AI Infrastructure Engineer**
Building systems where AI behavior is predictable, costs are controlled, and data models don't lie.

I design and ship backend infrastructure with a focus on reliability and correctness — AI routing systems that control inference cost, prompt runtimes that make model behavior auditable, and financial tools built on integer arithmetic instead of floating-point optimism. My projects reflect a consistent preference for systems that fail loudly, log honestly, and scale without accumulating hidden technical debt.

---

## Featured Projects

**[GPCGuard](https://www.gpcguard.app)** *(public release in progress)*
Privacy compliance is a legal requirement, but most engineering teams have no systematic way to verify it. GPCGuard is a GPC/CCPA compliance SaaS that detects and reports on Global Privacy Control opt-out signals as required under CCPA/CPRA, CPA, CTDPA, and NJDPA. It includes a Python scanner suite, Stripe billing, a Next.js 16 dashboard, and Supabase Edge Functions on the backend. Security audit complete.

**[Babel](https://github.com/gthgomez/Babel)**
AI systems fail in production not because the model is wrong, but because prompt behavior is inconsistent, unversioned, and impossible to audit. Babel is a prompt runtime that enforces deterministic, reproducible AI behavior — using a layered instruction stack with a catalog-driven resolver that compiles prompts consistently across deployments, a typed v9 router contract that enforces interface stability, a read-only MCP control-plane for external observability, and a regression test suite that catches behavioral drift before it reaches users.

**[Prismatix](https://github.com/gthgomez/Prismatix)**
Running every prompt through the most capable model is expensive and slow. Most routers pick models statically — Prismatix enforces routing decisions at runtime based on measured complexity, with budget constraints applied server-side before a request completes and consistent SSE streaming across all providers. It routes across Anthropic, OpenAI, Gemini, NVIDIA, and DeepInfra, and includes a multi-step debate pipeline for high-stakes outputs, a video processing pipeline, and long-term memory across sessions.

**[MonteCarlo-Ledger](https://github.com/gthgomez/MonteCarlo-Ledger)**
Personal finance software that rounds incorrectly or simulates with too few runs gives you false confidence in your projections. MonteCarlo-Ledger is a personal finance CLI with a SQLite backend that stores all monetary values as integer cents — eliminating floating-point rounding errors at the data layer — and runs 500 deterministic Monte Carlo simulations to generate safe-to-spend projections grounded in variance, not averages.

---

## Proof of Work

These projects are designed to be verifiable, not just described. Below is how they behave in practice.

---

### Prismatix — Model Routing in Practice

**What actually happens:**

- A simple query (e.g. "summarize this text") is routed to a low-cost model (Haiku / Flash)
- A complex task (e.g. code generation or multi-step reasoning) is routed to higher-tier models (Sonnet / Gemini Pro / Opus)
- All responses stream through a single normalized SSE interface regardless of which provider handles the request
- Each request is tracked against a server-side budget — limits are enforced before the request completes, not after

**What to look for in the code:**

- Deterministic routing decisions based on complexity scoring
- No provider-specific branching in client-facing code
- Consistent streaming output regardless of backend model
- Budget enforcement at the server layer, not the client

<!-- Add screenshot: routing decision log showing input complexity score + model selected -->
<!-- Add screenshot: budget enforcement block response -->
<!-- Suggested tool: Asciinema or terminal screenshot -->

---

### Babel — Deterministic AI Execution

**What actually happens:**

- A task is compiled into a structured instruction plan before any model call is made
- The compiled plan is validated against constraints before execution begins
- If the plan is incomplete, underspecified, or violates interface contracts → execution is blocked with an explicit failure state, not silently degraded
- Only validated plans reach the execution phase

**What to look for in the code:**

- Compile → Validate → Execute flow enforced on every request
- No direct model execution without a validated instruction plan
- Regression test suite verifying output stability across prompt changes
- Reproducible outputs given identical inputs and catalog state

<!-- Add screenshot: terminal output showing a validation failure with explicit error reasoning -->
<!-- Add screenshot: regression test run output -->

---

### MonteCarlo-Ledger — Correctness Over Convenience

**What actually happens:**

- All monetary values are stored as integer cents — no floating-point arithmetic at the data layer
- Income and expenses are projected forward across a 90-day horizon
- 500 deterministic Monte Carlo simulations stress-test each projection
- The system outputs a safe-to-spend value derived from worst-case scenario distribution, not simple averages

**What to look for in the code:**

- Integer-only money storage throughout — no `float` for currency values
- Deterministic simulation seeding — identical inputs produce identical projections
- Clear separation between raw ledger data and derived projection output
- No hidden state or mutation affecting simulation results

<!-- Add screenshot: full CLI run — add transaction → run projection → safe-to-spend output -->
<!-- Add screenshot: two runs with identical inputs producing identical output -->

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
Integer money storage, compiled prompt structures, typed router contracts. Correctness bugs at the data layer propagate everywhere; fix them at the source.

---

## Key Tradeoffs

Specific decisions made across these projects — what I chose, what I ruled out, and where the current design has limits.

**Prismatix: runtime routing over static configuration**
Routing could have been a config file — map task types to models at deploy time. I built runtime scoring instead because static config can't adapt to prompt length, context depth, or mixed-intent queries. The tradeoff is added latency on the scoring step and a complexity score that needs tuning. What I intentionally left out: automatic model fallback on provider failure. That's the right next addition, but adding it without proper logging first would make failures harder to diagnose, not easier.

**Babel: compiled instruction plans over direct prompt injection**
The simpler approach is to concatenate system prompts at request time. Babel compiles a validated instruction plan first because direct injection makes prompt behavior dependent on call-site logic, which breaks as soon as anyone adds a new code path. The tradeoff is a heavier request path. Where it breaks: the catalog resolver assumes instruction entries are stable between deployments — hot-swapping catalog entries mid-session is not currently safe.

**MonteCarlo-Ledger: integer cents over decimal types**
Most finance software uses `DECIMAL` or `float` for readability. I use integer cents because rounding behavior in `DECIMAL` arithmetic is database-specific and `float` accumulates error across summation. The tradeoff is that every input and display layer must convert explicitly — there's no implicit formatting. What I intentionally did not build: multi-currency support. Adding it correctly requires exchange-rate versioning tied to transaction timestamps, which is a separate system; adding it naively would corrupt historical projections.

---

## What I Would Improve in Production

- Add full request/response tracing dashboards for Prismatix (latency and cost per route, per provider)
- Introduce persistent execution logs and replay tooling for Babel to support post-hoc debugging
- Expand MonteCarlo-Ledger to support real-time data ingestion and user-configurable scenario parameters

---

## Where to Start

| Repo | What it demonstrates |
|---|---|
| **Babel** | Systems design thinking — constraints, contracts, auditability |
| **Prismatix** | Production tradeoff reasoning — cost, latency, provider abstraction |
| **GPCGuard** | End-to-end product delivery — compliance domain, full-stack, shipped |
| **MonteCarlo-Ledger** | Data correctness mindset — determinism, clean schema design |

Babel and Prismatix are the most architecturally complex. GPCGuard is the most complete product. MonteCarlo-Ledger is smaller but demonstrates a data-correctness mindset that shows up consistently across all of the work.

---

## Stack

Python · TypeScript · Rust · React · Next.js · SQLite · Supabase · Deno · Android (Jetpack Compose)

---

## Currently Focused On

Backend systems, AI infrastructure, and applied ML tooling. Open to internship and early-career roles in software engineering, ML infrastructure, or backend development.

[LinkedIn](https://linkedin.com/in/gthgomez)

## License

This profile repository is publicly viewable for portfolio and project-navigation purposes. It is not open source. See [LICENSE.md](LICENSE.md) for permitted use. Referenced projects and third-party materials retain their own licenses.

