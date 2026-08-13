## Context

The maintained backend gate currently keeps its selected test list in two
workflow files. `test.sh preflight` generates tracked OpenAPI artifacts in
place, and the browser gate invokes the complete `core` project before
invoking selected core specs again. These are test-system concerns rather than
product behavior and need deterministic, repository-local contracts.

## Goals / Non-Goals

**Goals:**
- Keep one maintained backend manifest for both CI jobs.
- Verify generated OpenAPI outputs without changing tracked files.
- Make default browser-stage membership explicit and non-overlapping.
- Keep frontend coverage focused on production sources.

**Non-Goals:**
- Raising coverage thresholds or admitting legacy full-suite failures.
- Replacing browser acceptance tests with lower-level tests.
- Changing application APIs, generated artifact formats, or provider behavior.

## Decisions

- A shell helper owns the maintained test list and accepts a `test` or
  `coverage` mode. Workflows call it rather than duplicate file arguments.
  This retains the existing test membership while eliminating list drift.
- Preflight uses a directory under `TEST_RUN_DIR`, exports the schema there,
  generates declarations there, and compares both files with tracked output.
  A temporary path is preferable to restoring files because interruption cannot
  leave the worktree dirty.
- The browser gate runs the full `core` project once and separately runs only
  selected AI-heavy regressions. Named core commands are removed because they
  are already members of `core`.
- Jest excludes test directories from coverage collection. Production route
  modules remain in scope; diagnostic routes are not broadly excluded.

## Risks / Trade-offs

- [Script becomes a shared CI dependency] → Add static regression tests for
  both workflow callers and both execution modes.
- [Generated output comparison needs temp directories] → Reuse the existing
  per-worktree `TEST_RUN_DIR` and create it before preflight.
- [Removing duplicate E2E commands reduces repeated signal] → Preserve the
  complete core project and retain explicit AI-heavy regression commands.
