# Engineering Case Study: ProofPath

**Offline-first CS learning application with executable coding lessons, local progress tracking, and provenance-aware portfolio evidence.**

[![ProofPath Lesson Screen](../../assets/showcase/proofpath-lesson.jpg)](../../assets/showcase/proofpath-lesson.jpg)

## 1. Problem Being Solved

Most online computer science education platforms suffer from three structural shortcomings:
1. **Passive Video Watching**: Learners watch lectures or read tutorials without executing real code, leading to an illusion of competence that breaks down when confronted with a real terminal.
2. **Server-Dependent Execution**: Existing interactive learning platforms rely on expensive cloud sandboxes. If the student has poor internet connectivity or travels offline, the learning environment stops functioning entirely.
3. **Unverifiable Progress Claims**: Students complete online courses and receive unverified PDF certificates that recruiters cannot independently audit, verify, or inspect for code authenticity.

ProofPath solves these challenges by combining an **offline-first local execution sandbox** with **cryptographically verifiable portfolio evidence receipts**.

## 2. Intended Users

- **Computer Science Students & Self-Taught Learners**: Students who need hands-on, test-driven programming exercises that run smoothly on laptops, tablets, or phones without requiring persistent cloud connections.
- **Bootcamp & Course Instructors**: Educators looking for structured, deterministic grading and offline progress tracking for curriculum delivery.
- **Hiring Managers & Technical Recruiters**: Evaluators who want to inspect reproducible proof that a candidate solved algorithmic coding challenges independently.

## 3. Why the Problem Is Technically Difficult

1. **Sandboxed In-Browser/In-App Code Execution**: Executing user-written Python code client-side without a remote backend requires compiling Pyodide (WebAssembly) or WebWorkers safely, enforcing execution time limits, preventing infinite loops from locking the UI thread, and intercepting standard I/O (stdout/stderr).
2. **Cross-Platform Responsive UX (Mobile & Desktop Web)**: Code editors typically fail on mobile screens due to virtual keyboard collisions, poor touch cursor selection, and cramped layouts. Designing a dual-surface touch-friendly syntax editor and desktop split-pane IDE in React Native / Expo requires meticulous UI engineering.
3. **Tamper-Resistant Progress & Evidence Export**: Exported completion receipts must link the learner's submitted source code, test outputs, execution duration, and cryptographic file hashes so an external reviewer can verify the submission without trusting client claims.

## 4. Architecture and Major Subsystems

[![ProofPath Passing Check](../../assets/showcase/proofpath-passing.jpg)](../../assets/showcase/proofpath-passing.jpg)

```mermaid
flowchart TD
    User["Learner Interface (Mobile / Web)"] --> Navigation["Career Paths & Lesson Stepper"]
    Navigation --> Editor["Code Lab Syntax Editor"]
    
    subgraph Sandbox ["Local Execution Sandbox"]
        Worker["Background Execution Worker (WebWorker / Native Thread)"]
        WASM["Pyodide WebAssembly Python Runtime"]
        Policy["Execution Policy & Watchdog Timer"]
        
        Worker --> WASM
        Worker --> Policy
    end
    
    Editor --> Sandbox
    Sandbox --> Verifier["Test Runner & Assertion Evaluator"]
    
    subgraph Persistence ["Offline Storage & Evidence Engine"]
        Store["Local Progress Store (SQLite / AsyncStorage)"]
        Provenance["Evidence Generator & Hash Verifier"]
        Export["Signed Evidence Receipt (.json)"]
        
        Store --> Provenance
        Provenance --> Export
    end
    
    Verifier --> Persistence
```

- **Curriculum & Career Path Engine**: Organizes lessons into structured engineering tracks (Python Fundamentals, Object-Oriented Design, Data Structures, Algorithms) with progressive unlocking and prerequisite gating.
- **Touch-Friendly Code Lab**: React Native editor featuring syntax highlighting, virtual indentation keys, line numbering, and inline error diagnostic callouts.
- **Client-Side Execution Worker**: Executes Python code in a dedicated worker thread using WebAssembly, isolating execution memory from the primary UI render loop.
- **Deterministic Assertion Verifier**: Automatically executes invisible grading test suites against learner functions to verify correctness, boundary edge cases, and algorithmic complexity.
- **Evidence Receipt Generator**: Produces machine-readable JSON receipts containing SHA-256 code digests, test pass receipts, timestamped run records, and verification proofs.

## 5. Important Engineering Decisions

- **Offline-First by Design**: All core curriculum content, test runners, and WebAssembly binaries are bundled locally into the client. Learners can study, code, and pass verification checks on an airplane with zero network access.
- **Local Progress Persistence**: Progress is stored in an encrypted local database with support for JSON migration and backup export/restore, ensuring students never lose completed milestones.
- **Dual Verification (Run File vs. Run Checks)**: Learners have access to two distinct execution modes: "Run File" outputs standard terminal stdout for interactive experimentation, while "Run Checks" executes the authoritative unit grading suite without leaking answers.

## 6. Alternatives and Tradeoffs

| Alternative Considered | Chosen Approach | Rationale |
|---|---|---|
| Server-Side Cloud Containers (Docker) | Local WebAssembly (Pyodide) Execution | Eliminates cloud hosting costs, prevents server downtime, operates offline, and guarantees infinite horizontal scalability. |
| Multiple Choice Quizzes | Test-Driven Code Implementation | Multiple-choice questions test memorization; test-driven coding proves actual programming competence. |
| Web-Only SPA | Cross-Platform React Native (Expo) | Enables native mobile Android/iOS deployment alongside responsive desktop web browsing. |

## 7. Interesting Implementation Details

- **Watchdog Timeout Protection**: User-submitted code is monitored by a strict watchdog timer. Infinite loops (`while True: pass`) are preemptively aborted, returning a friendly timeout diagnosis without freezing the device.
- **Sanitized Workspace Evidence**: Exported evidence manifests omit private device markers while preserving cryptographic verification hashes, making them safe to share publicly on GitHub or LinkedIn.

## 8. Reproducible Tests and Validation

The project maintains extensive automated test suites:
- **Sandbox Security & Timeout Tests**: Validate that unauthorized file system escapes and runaway loops are properly confined.
- **Curriculum Integrity Tests**: Static analysis ensuring all curriculum lessons have valid starter templates, test assertions, and reachable prerequisites.
- **UI Accessibility & Scale Checks**: Verify font scaling, dark/light contrast ratios, and touch target dimensions.

Over 550 tests execute via Vitest:
```powershell
npm test -- --run
```

## 9. User-Facing Demonstration

In the application:
1. Select a learning track (e.g., Python Core).
2. Open an introductory lesson (e.g., Variable Assignment & Conditionals).
3. Review the conceptual prompt and inspect the starter code in the Code Lab editor.
4. Execute "Run Checks" on incomplete code to observe failing unit assertions with diagnostic explanations.
5. Implement the solution and re-run checks to achieve a verified green pass.
6. Export a signed portfolio evidence receipt proving independent milestone completion.

[![ProofPath Career Path Selection](../../assets/showcase/proofpath-choose.jpg)](../../assets/showcase/proofpath-choose.jpg)

## 10. Current Limitations

- **Language Scope**: Client-side WebAssembly execution currently focuses on Python and TypeScript; compiled languages (C++, Rust) require separate toolchain support.
- **Initial WASM Load Time**: On slow mobile devices, the initial download and compilation of the Pyodide WebAssembly runtime takes several seconds before first-run caching takes effect.

## 11. Specific Contributions and AI-Assisted Workflow

- **Engineering Direction**: Conceived the offline-first educational architecture, designed the evidence provenance protocol, architected the React Native component hierarchy, and specified grading assertions.
- **AI Agent Pairing**: Used coding agents to draft modular lesson units, generate comprehensive test assertions, implement responsive styling across viewport breakpoints, and test accessibility properties.

## 12. Links and Verification References

- **Canonical Repository**: [https://github.com/gthgomez/ProofPath](https://github.com/gthgomez/ProofPath)
- **Live Preview & Test Documentation**: [https://github.com/gthgomez/ProofPath/blob/main/docs/README.md](https://github.com/gthgomez/ProofPath/blob/main/docs/README.md)
