# Jonathan Gomez Aguilar — gthgomez

I build AI orchestration systems, prompt infrastructure, and practical software tools.

---

## Featured Projects

### [Prismatix](https://github.com/gthgomez/Prismatix)
An AI model router across Anthropic, OpenAI, Gemini, NVIDIA, and DeepInfra. A heuristic complexity scorer analyses each query and routes to the right model tier — Llama 4 Scout / Haiku for quick lookups, Sonnet for code, Flash for general use, Qwen3-235B / Opus / Gemini Pro for deep analysis. Streams SSE from all providers through a single normalised client. Includes debate mode (parallel challenger models + synthesis), an SMD pipeline (Draft → Skeptic → SynthDecision → Formatter), long-term memory via conversation summarisation, server-enforced daily budget tracking against Supabase `cost_logs`, and a video pipeline. Built with TypeScript on Vite + Deno edge functions.

### [Babel](https://github.com/gthgomez/Babel)
A prompt operating system for multi-model AI workflows. Babel provides a layered instruction stack — behavioral rules, domain expertise, model adapters, and project overlays — that routes tasks to the right prompt context before any model sees them. Includes a catalog-driven resolver/compiler, a typed `v9` router contract, a read-only MCP control-plane surface, and a full regression test suite. Designed for developers who want deterministic, auditable AI behavior across Claude, GPT, and Gemini.

### [MonteCarlo-Ledger](https://github.com/gthgomez/MonteCarlo-Ledger)
A personal finance CLI with a ledger-first SQLite backend and a Monte Carlo risk engine. Calculates a deterministic safe-to-spend value by projecting income and bills 90 days forward, then stress-tests that projection across 500 simulated scenarios. All monetary values are stored as integer cents — no float drift.

---

## Current Focus

- Multi-provider AI routing and streaming infrastructure
- Prompt infrastructure and AI orchestration tooling
- Evidence-gated self-learning systems for LLM workflows
- Practical local-first software with clean data models

---

## What's Public Here

| Repo | What it is | Stack |
|------|-----------|-------|
| [Prismatix](https://github.com/gthgomez/Prismatix) | Multi-provider AI router — Anthropic, OpenAI, Gemini, NVIDIA, DeepInfra | TypeScript, Deno, Supabase |
| [Babel](https://github.com/gthgomez/Babel) | Prompt OS — layered instruction stack for multi-model AI | TypeScript |
| [MonteCarlo-Ledger](https://github.com/gthgomez/MonteCarlo-Ledger) | Personal finance CLI with Monte Carlo risk simulation | Python, SQLite |

---

## How to Navigate This Profile

- Start with **Prismatix** if you're interested in multi-provider AI routing, SSE streaming, cost tracking, or Supabase edge functions.
- Start with **Babel** if you're interested in prompt engineering, LLM orchestration, or AI workflow infrastructure.
- Start with **MonteCarlo-Ledger** if you're interested in financial modeling, CLI tooling, or SQLite-backed applications.
- This repo (`gthgomez`) is the profile landing page — nothing to run here.
