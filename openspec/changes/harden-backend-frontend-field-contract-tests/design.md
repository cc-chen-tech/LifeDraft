## Context

The repository has substantial test volume, but several high-risk runtime pathways
still have weak contract coverage:

- Gameplay context selection (`NarrativeManager`, `HistoricalSummarySelector`).
- SSE edge paths for retries, reconnection caching, prefetch, and async side effects.
- Session recovery and image-health checks (`SessionService`) including era parsing, missing-file reconciliation, and background scheduling.

Recent bugs showed that those paths can pass functionally while still violating hidden
state contracts (empty/null fields, missing branch behavior, or silently skipped retries).
Since `maintained` coverage is below target, we should first harden these contract points
with focused tests before broad refactors.

## Goals / Non-Goals

**Goals:**
- Add only test files that assert field/state contracts and boundary behavior.
- Cover high-risk untested branches in backend gameplay/SSE/session services with deterministic assertions.
- Keep tests fast and isolated (mock heavy external calls where possible).
- Keep each test focused on a specific contract requirement.

**Non-Goals:**
- No production feature changes.
- No frontend behavior refactors in this iteration.
- No broad API schema redesign unless a failing test first proves an actual regression.

## Decisions

- Use dedicated new test modules to avoid changing existing tests (`tests/test_contracts_backend_field_hardening.py`,
  `tests/test_contracts_session_service_hardening.py`, `tests/test_contracts_sse_helpers_hardening.py`).
- Favor patching internal helpers and collaborators (`ImageClient`, `ImageStorageService`, `RoundIllustrationService`, background thread pool)
  so tests run without real I/O or external services.
- Focus on deterministic behavior for random/async branches by patching `random.random` and
  capturing whether background jobs are enqueued, not by asserting exact payloads.
- Keep assertions on concrete contracts: non-crash, status transition, expected field presence,
  and side-effect triggers.

## Risks / Trade-offs

- [Risk] Private helper testing can become fragile if internal names change.  
  [Mitigation] Restrict tests to stable entrypoints and verify key behaviors, not implementation-only sequencing.
- [Risk] Threaded background scheduling is timing-sensitive.  
  [Mitigation] Patch thread pool/submissions and use call counts/assertions that do not depend on execution timing.
- [Risk] Too many contract tests can slow the suite if DB-backed operations are overused.  
  [Mitigation] Keep DB-backed assertions minimal and prefer mock state objects for module-level branches.

## Migration Plan

- Implement and run the new contract tests in this branch.
- If failures reveal a real behavior bug, patch production code in a follow-up change (not within this scope).
- After this change, re-run `pytest` subsets and record coverage deltas for `maintained` suite.
