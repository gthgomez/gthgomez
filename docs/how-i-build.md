# How I Build — Methodology

Short version: claims are bound to evidence, evidence is bound to a source
SHA, and anything that cannot be verified is labeled as such instead of
inferred. This page is the working methodology for this account; the
project-by-project index lives in [project-index.md](project-index.md).

## Principles

1. **Claims follow evidence, not the reverse.** A sentence in a README is
   either verifiable from linked public source, backed by an evidence
   receipt, or explicitly labeled as a non-public case study.
2. **Evidence receipts, not prose totals.** Test counts, coverage and
   benchmark numbers belong in generated receipts with `source_sha`,
   dependency digests, environment and per-check states — not copied into
   prose where they silently go stale.
3. **Explicit status vocabulary.** Every check reports one of
   `PASS, FAIL, BLOCKED, NOT_RUN, UNKNOWN, INCONCLUSIVE`. Nothing defaults
   to PASS by being omitted, and `UNKNOWN`/`NOT_RUN` never render as green.
4. **Stale evidence stays historical.** A cached PASS from an old SHA is a
   historical PASS; it is never silently recertified for new source.
5. **Negative controls.** Every gate gets at least one deliberately broken
   fixture that must fail with a named rule. A check that has never failed
   is not a check.

## The hygiene checker

`tools/portfolio_hygiene.py` is an offline, deterministic, standard-library
Python checker. It reads files only; it never executes README snippets,
workflow contents, or URLs, and it never touches the network (remote probing
is a separate trusted mode that does not exist yet).

```bash
python tools/portfolio_hygiene.py check --repo . --config portfolio-manifest.json
```

Exit codes: `0` clean, `1` findings, `2` invalid configuration or tool
failure. Rules H001–H008 cover workstation-path leakage, markdown link and
anchor resolution, workflow badges, license coherence, version consistency,
evidence-receipt validity, volatile prose and the approved-command registry.
The registry lists commands; the checker verifies that they reference real
scripts and files but does not execute them — clean-install CI remains the
behavioral authority.

## A real positive example

PF01 (this repository) corrected account-level README claims that overstated
determinism and device qualification. The correction is verifiable: each
changed sentence names its evidence, and claims that cannot be verified from
public source (for example GPCGuard) are labeled non-public case studies
rather than implied to be tested.

## A real falsifying example

The checker's own fixtures contain a receipt marked `current` whose
`source_sha` is an old commit while a check reports `PASS`. H006 must reject
it — exit 1 with a finding stating that a cached PASS stays historical.
This negative control fails today by construction, and the fixture test
`test_stale_sha_marked_current_fails` asserts exactly that. If someone later
"fixes" the checker into always passing, this test fails first.

## Known limitations

- The checker is local-only. Remote link/deployment probing is deliberately
  out of scope until a trusted scheduled mode with allowlists exists.
- H008 cannot prove arbitrary shell commands work; it only validates the
  registry against real scripts/files. CI executes commands, not the checker.
- Fixtures do not claim full Markdown-parser coverage; they cover the
  documented negative controls and the deterministic JSON ordering.
