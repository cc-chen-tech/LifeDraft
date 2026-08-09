## Context

The maintained backend suite is intentionally limited to deterministic, provider-free tests, but several high-value state contracts remain outside it. The selected suites use concrete `PlayerState`, local database fixtures, and deterministic in-process collaborators.

## Goals / Non-Goals

**Goals:**
- Make continuity, wealth, finalization, and persisted player-state regressions fail in both maintained workflows.
- Keep the two workflow test lists byte-for-byte ordered equivalents.
- Retain the current global threshold while measuring the real coverage contribution.

**Non-Goals:**
- Change production behavior, existing test sources, or the global threshold.
- Add providers, browser execution, network access, or mock-based tests to the gate.

## Decisions

- Promote the four existing suites as a coherent state-authority group rather than splitting individual tests. They share only deterministic state and database boundaries, and their combined `103` tests complete in under one second without coverage.
- Append them after the existing maintained state-contract suites in both workflows. Ordered parity keeps the two CI paths equivalent and reviewable.
- Re-run hygiene, direct tests, full coverage, and strict OpenSpec validation before committing. Static safety is retained even when test files do not use mocking APIs.

## Risks / Trade-offs

- [Local database fixture assumptions] → Run the exact selected suite and the complete maintained gate with CI environment variables.
- [Broader gate duration] → The measured standalone suite is sub-second without coverage, so the added runtime is small relative to the existing gate.
- [False confidence from global coverage] → Report per-module coverage for continuity, wealth, finalizer, and player-state modules alongside the global result.
