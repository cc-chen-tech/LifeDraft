## Context

The maintained backend test selection is intentionally smaller than the full
suite, but it measures the whole `src` tree. It must grow through small,
repeatable batches rather than by admitting external provider or timing-heavy
tests. The current branch has already covered world-model, collection,
illustration, SSE framing, and prompt fallback paths; the next uncovered
high-risk contracts are pure local transforms or route safeguards.

## Goals / Non-Goals

**Goals:**
- Add only new test files for observable behavior in four high-risk areas.
- Exercise fallback fields, request safeguards, parser normalization, and
  music metadata eligibility with local data only.
- Promote candidates only after two passing focused runs and measure the
  expanded maintained workflow twice with `--cov=src`.

**Non-Goals:**
- Changing any production behavior or existing test.
- Running real AI, image, music, network, or browser-provider calls.
- Claiming that the resulting batch establishes global 70% backend coverage.

## Decisions

### Assert outputs and state, not collaborator calls

The event fallback suite constructs the real `RoundEventGenerator` with no AI
generator. Route protocol tests use real FastAPI request objects and concrete
connection manager instances. Parser and music helpers receive parsed strings,
plain dictionaries, or temporary files. Assertions therefore cover response
content and state rather than mocked call topology.

### Exclude an identified production behavior gap

The prior remediation branch included a nested fallback-setting test that
currently fails because `RoundEventGenerator._extract_setting_text` can choose
an unrelated scalar from a nested payload. This test-only change retains
stable flat-shape contracts and documents the nested case as a future
production repair, instead of silently changing product behavior.

### Preserve workflow symmetry

Both workflow file lists are parsed and diffed before commit. New candidates
are appended in the same order only after two focused passing runs.

## Risks / Trade-offs

- [Risk] Copied local tests might no longer match current code. → Mitigation:
  run focused suites twice before workflow edits and do not cherry-pick source
  or existing-test changes.
- [Risk] Route tests can accidentally depend on environment flags. →
  Mitigation: use only explicit request inputs and local temporary environment
  control; avoid network or session setup.
- [Risk] Metadata helper contracts can duplicate production algorithms. →
  Mitigation: assert user-facing eligibility and normalization results rather
  than intermediate implementation details.

## Migration Plan

1. Add focused tests and validate them twice.
2. Promote stable files to both maintained workflows.
3. Measure the full `src` denominator twice and retain the existing gate if
   the next integer floor is not reproduced.
4. Commit this batch independently, keeping full-suite execution for the
   main-release policy.
