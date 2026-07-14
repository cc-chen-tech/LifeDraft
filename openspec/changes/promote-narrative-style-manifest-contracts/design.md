## Context

The maintained gate is expanded only with stable, independent tests. The
StyleManifest suite uses pytest-managed temporary directories to exercise
local files, serializer boundaries, caches, and invalid style data. It runs 19
tests with 91% direct module coverage and has no network, environment mutation,
or mock-framework dependencies.

## Goals / Non-Goals

**Goals:**
- Execute the deterministic StyleManifest suite in both maintained workflows.
- Keep the two selections ordered-identical.
- Test a 51% maintained threshold only after the normal current-threshold gate
  succeeds.

**Non-Goals:**
- Change existing tests, source behavior, or persistent style assets.
- Treat temporary-directory tests as integration tests needing a live service.
- Raise the threshold without a passing full maintained execution.

## Decisions

- Promote the existing suite as-is because pytest's `tmp_path` isolates every
  local file operation and it covers meaningful data-boundary behavior.
- Place the file after the other narrative-engine suites in both selections.
- Attempt a 51% threshold after the 50% baseline passes, since the suite's
  direct coverage is high enough to make the next global milestone plausible.

## Risks / Trade-offs

- [Filesystem behavior differs in CI] → The suite uses only pytest's local
  temporary directory and is run under CI-like settings before commit.
- [Parity diverges] → Parse and diff both workflow selections.
- [51% remains too high] → Keep the verified 50% threshold and record the
  actual measured result rather than weakening the test selection.
