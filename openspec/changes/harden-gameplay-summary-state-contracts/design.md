## Context

The gameplay summary router returns the state consumed by browser save/resume flows and prepares life summaries from current in-memory history. Most uncovered behavior is deterministic once a session contains a real game loop and player state; the only external boundary is text completion, which already has a grounded fallback.

## Goals / Non-Goals

**Goals:**
- Verify serialized state retains progress, active event, and narrative-style fields.
- Verify summary history uses complete round content, bounds selected weeks, and falls back safely without an AI provider.
- Exercise the router through the real session store and no network calls.

**Non-Goals:**
- Change session restoration, summary prose, or ending evaluation behavior.
- Call an LLM, run a browser, or alter existing tests.
- Treat provider output quality as a deterministic contract.

## Decisions

- Install a real `GameLoop` in the session store for state response tests. This validates the same object and serialization logic used by the API, while avoiding database restoration as a separate concern.
- Use a minimal local completion collaborator that raises an exception to select the documented grounded-fallback branch. This tests the error boundary without a mock framework or provider credentials.
- Build histories from real `PlayerState` dictionaries and assert response facts, not exact generated prose. The fallback is allowed to evolve while its factual inputs, bounds, and nonempty output remain contractual.
- Remove each test session from the shared store in `finally` to avoid coupling parallel cases.

## Risks / Trade-offs

- [Session store is process-global] -> clean each exact game/user identity in `finally`.
- [Grounded fallback wording can evolve] -> assert invariant facts and response structure rather than incidental punctuation.
- [Direct router calls omit HTTP auth middleware] -> ownership/auth remains covered by route integration tests; this batch targets response semantics after a session is resolved.

## Migration Plan

No data or runtime migration is needed. The change adds maintained tests and workflow registration only; reverting removes these additions.
