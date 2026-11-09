# Portfolio Repository Inventory & Evaluation

This document provides a comprehensive, structured inventory of all repositories under the GitHub account `gthgomez`, establishing clear boundaries between original flagship software, companion platforms, developer tools, upstream forks, and private research projects.

---

## 1. Executive Summary

| Category | Public | Private | Total | Description |
|---|---|---|---|---|
| **Flagship Systems** | 6 | 0 | 6 | Primary technical showcases with verified implementations and case studies. |
| **Companion Applications** | 3 | 0 | 3 | Mobile/Android shells and companion surfaces paired with flagship cores. |
| **Supporting Tools & Utilities** | 4 | 0 | 4 | Purpose-built developer CLIs, image fixers, and hardware remotes. |
| **Interactive Games** | 5 | 0 | 5 | Original web games and Godot game engine prototypes. |
| **Public Web Origin Surfaces** | 1 | 0 | 1 | Official landing and verification portals (`babel-origin-site`). |
| **Profile & Portfolio Meta** | 1 | 0 | 1 | Profile configuration, hygiene automation, and portfolio documentation (`gthgomez`). |
| **Upstream Forks** | 2 | 0 | 2 | Upstream open-source contributions and forks (`connect`, `rea`). |
| **Private Incubation & Research** | 0 | 43 | 43 | Commercial SaaS pipelines, private research spikes, and archived prototypes. |
| **Total Account Inventory** | **21** | **44** | **65** | Fully accounted repository baseline. |

---

## 2. Flagship Systems

These six systems represent the core of the public engineering portfolio. Each is backed by an authentic codebase, automated test suites, and an in-depth technical case study.

### 1. [Babel](https://github.com/gthgomez/Babel)
- **Role**: Flagship 1 — AI Agent Infrastructure & Verified Execution
- **Stack**: TypeScript, Node.js, Electron, SQLite FTS, Tree-Sitter
- **Interfaces**: CLI, Terminal TUI, Electron Desktop Application
- **Key Engineering Distinction**: Solves agent hallucinatory completion by enforcing evidence-bound task verification, machine-readable execution receipts, and layered operational prompts.
- **Case Study**: [Babel Technical Case Study](case-studies/babel.md)
- **Deployment / Release**: [Latest GitHub Releases](https://github.com/gthgomez/Babel/releases/latest)

### 2. [MonteCarlo-Ledger](https://github.com/gthgomez/MonteCarlo-Ledger)
- **Role**: Flagship 2 — Backend Engineering, Mathematical Modeling & Data Integrity
- **Stack**: Python 3.10+, SQLite, FastAPI, Hypothesis, Pydantic
- **Interfaces**: Interactive CLI, Local REST API, Web Visualizer
- **Key Engineering Distinction**: Two-stage forecasting architecture that combines deterministic calendar bill pacing with seeded Monte Carlo stochastic risk modeling and integer-cents accounting.
- **Case Study**: [MonteCarlo-Ledger Technical Case Study](case-studies/monte-carlo-ledger.md)
- **Deployment**: [Live Web Visualizer](https://montecarlo-ledger.vercel.app)

### 3. [Prismatix](https://github.com/gthgomez/Prismatix)
- **Role**: Flagship 3 — Full-Stack AI Routing, Streaming & Cost Governance
- **Stack**: TypeScript, Vite, React, Deno Edge Functions, Supabase Postgres
- **Interfaces**: Responsive Web Application (Desktop & Mobile)
- **Key Engineering Distinction**: Multi-provider AI chat gateway featuring explainable model routing, real-time Server-Sent Events (SSE) streaming, and fail-closed budget controls.
- **Case Study**: [Prismatix Technical Case Study](case-studies/prismatix.md)
- **Deployment**: [Live Production Application](https://prismatix-app.vercel.app)

### 4. [GBA_Emulator](https://github.com/gthgomez/GBA_Emulator)
- **Role**: Flagship 4 — Systems Programming, Computer Architecture & Emulation
- **Stack**: C++17, CMake, SDL3, Google Oboe (Android bridge)
- **Interfaces**: Native SDL3 Desktop Window, Headless Verification Lab, Android Native Shell
- **Key Engineering Distinction**: Portable Game Boy Advance emulator core featuring cycle-stepped ARM7TDMI dual-ISA execution, memory waitstate modeling, 2D scanline PPU rasterization, and public mGBA test suite conformance.
- **Case Study**: [GBA_Emulator Technical Case Study](case-studies/gba-emulator.md)
- **Documentation**: [Conformance Baseline & Status](https://github.com/gthgomez/GBA_Emulator/blob/main/docs/open-issues-status.md)

### 5. [ProofPath](https://github.com/gthgomez/ProofPath)
- **Role**: Flagship 5 — Offline-First Learning Systems & Executable Verification
- **Stack**: TypeScript, React Native, Expo, Pyodide (WebAssembly), SQLite
- **Interfaces**: Cross-Platform Mobile & Desktop Web Application
- **Key Engineering Distinction**: Hands-on computer science learning application with local client-side WebAssembly code execution, automated grading assertions, and tamper-resistant evidence export.
- **Case Study**: [ProofPath Technical Case Study](case-studies/proofpath.md)
- **Documentation**: [Project Architecture & Test Baselines](https://github.com/gthgomez/ProofPath/blob/main/docs/README.md)

### 6. [reliquary](https://github.com/gthgomez/reliquary)
- **Role**: Flagship 6 — Game Engine Development, Interactive Systems & PWA
- **Stack**: TypeScript, React, HTML5 Canvas, Vite, Tailwind CSS
- **Interfaces**: Responsive Browser PWA (Keyboard, Gamepad, Touch D-Pad)
- **Key Engineering Distinction**: Medieval-fantasy creature-binding RPG with turn-based combat mathematics decoupled from render animations, tile collision masks, safe-spawn algorithms, and offline PWA service workers.
- **Case Study**: [Reliquary Technical Case Study](case-studies/reliquary.md)
- **Deployment**: [Live Playable Application](https://reliquary-dusky.vercel.app)

---

## 3. Coherent Project Families

To avoid presenting fragmented repositories as disconnected efforts, related repositories are grouped into unified project families:

### Family A: The Babel AI Coding Agent Ecosystem
- **Core Runtime**: [`gthgomez/Babel`](https://github.com/gthgomez/Babel) — Main open-source repository containing CLI, TUI, and desktop client.
- **Public Origin Site**: [`gthgomez/babel-origin-site`](https://github.com/gthgomez/babel-origin-site) — Public static web showcase and verification portal.
- **Private Research & R&D**: `Babel-rnd`, `Babel-private` — Private research spikes, benchmarks, and experimental agent evaluation archives.

### Family B: The MonteCarlo Financial Architecture
- **Python Core & API**: [`gthgomez/MonteCarlo-Ledger`](https://github.com/gthgomez/MonteCarlo-Ledger) — Core double-entry ledger, deterministic cash-flow engine, and Monte Carlo simulator.
- **Android Mobile Companion**: [`gthgomez/MonteCarloLedger-Android`](https://github.com/gthgomez/MonteCarloLedger-Android) — Native Jetpack Compose mobile client providing deterministic bill pacing, offline SQLite storage, and AES-GCM encrypted backup interoperability.

### Family C: The Prismatix AI Gateway & On-Device Inference
- **Edge-Governed Web Gateway**: [`gthgomez/Prismatix`](https://github.com/gthgomez/Prismatix) — Full-stack multi-model chat with Deno edge routing, BYOK key encryption, and fail-closed budgets.
- **On-Device Android LLM**: [`gthgomez/PrismLocal`](https://github.com/gthgomez/PrismLocal) — Native Android application executing local GGUF quantized models on-device via llama.cpp JNI bindings with local RAG.

### Family D: The Game Boy Advance Emulation Platform
- **Emulation Core**: [`gthgomez/GBA_Emulator`](https://github.com/gthgomez/GBA_Emulator) — Portable C++17 core with SDL3 desktop host and deterministic headless test harness.
- **Android Native Shell**: [`gthgomez/GbaEmulatorAndroid`](https://github.com/gthgomez/GbaEmulatorAndroid) — Kotlin/NDK mobile dev shell integrating the core via JNI, SurfaceView rendering, and low-latency Oboe audio.

### Family E: Interactive Web & Mobile Games
- **Reliquary RPG**: [`gthgomez/reliquary`](https://github.com/gthgomez/reliquary) — Production-grade creature-taming RPG with custom Canvas rendering.
- **Dragon Wake**: [`gthgomez/DragonWake`](https://github.com/gthgomez/DragonWake) — Multiplayer web MMORTS strategy prototype featuring city construction and isometric maps.
- **GravityPivot**: [`gthgomez/GravityPivot`](https://github.com/gthgomez/GravityPivot) — Physics-based 2D orbital swing and navigation game.
- **ManaNet**: [`gthgomez/ManaNet`](https://github.com/gthgomez/ManaNet) — Cyberpunk tower defense game developed in Godot 4.
- **Orbitscar**: [`gthgomez/Orbitscar`](https://github.com/gthgomez/Orbitscar) — Sci-fi strategy prototype with deterministic tactical breaches.

### Family F: Native Mobile Utilities & Developer Tools
- **Scout**: [`gthgomez/Scout`](https://github.com/gthgomez/Scout) — Policy-governed developer CLI for identifying open-source bounty opportunities and assembling structured handoffs for coding agents.
- **RGRemote**: [`gthgomez/RGRemote`](https://github.com/gthgomez/RGRemote) — Local-network Android TV remote for Roku and Google TV with zero cloud, zero accounts, and zero tracking.
- **ExactUploadFixer**: [`gthgomez/ExactUploadFixer`](https://github.com/gthgomez/ExactUploadFixer) — Android utility resizing and compressing images to strict dimensional and file-size upload limits.
- **WallpaperCropFixer**: [`gthgomez/WallpaperCropFixer`](https://github.com/gthgomez/WallpaperCropFixer) — On-device wallpaper cropper with ML Kit face detection and correct EXIF orientation handling.

---

## 4. Upstream Open-Source Forks

The portfolio explicitly documents third-party forks to preserve clear provenance:

1. **[`connect`](https://github.com/gthgomez/connect)**
   - **Upstream**: `commaai/connect`
   - **Description**: Web client for managing openpilot driver-assistance devices. Public fork retained for exploration of comma.ai vehicle telemetry and device management.
2. **[`rea`](https://github.com/gthgomez/rea)**
   - **Upstream**: `morluto/rea`
   - **Description**: Reverse engineering framework utilizing autonomous agents. Retained as an upstream fork; custom enhancements and Windows-specific fixes are developed in isolated workspaces.

---

## 5. Private Incubation, Commercial SaaS & Research

The account includes 44 private repositories. In accordance with portfolio privacy policies, no proprietary source code, credentials, or internal infrastructure details are disclosed. High-level categories include:

- **Commercial SaaS & Compliance**: `GPCGuard`, `GPCGuard-public`, `AuditGuard` — Privacy compliance tools detecting Global Privacy Control (GPC) opt-out headers and generating compliance audit records.
- **Asset Pipelines & Game Tooling**: `gamedev`, `developertools-gameassets-ages` — Generative asset pipelines, sprite sheet compilers, and level authoring tools.
- **Smart TV Applications**: `Bible-Trivia-Night-TV`, `CouplesGameNightTV`, `Noche-de-Trivia` — Fire TV-first family trivia and interactive games developed in Kotlin/Android TV.
- **Cloud Agent Labs & Research Archives**: `cloud-agent-lab`, `cloud-agent-hub`, `personal-data-orchestrator`, `SimLife`, `PDFFixerPro` — Disposable cloud development workstations, financial simulation prototypes, and utility spikes.

---

## 6. Verification and Maintenance Policy

All public repositories are governed by the automated portfolio hygiene checker (`tools/portfolio_hygiene.py`). Every repository claim, link, and documentation asset must satisfy:
- Zero workstation or private absolute path leaks (H001).
- Complete relative markdown link validity (H002) and heading anchor integrity (H003).
- Strict non-volatile prose standards without drifting test counts or dynamic token prices (H007).
- License and security policy clarity across all public codebases.
