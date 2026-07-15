## Context

`GameLoopSession` and `SessionStore` preserve reconnect state outside the database. Their state transitions are deterministic when tested with inert objects rather than full game loops.

## Goals / Non-Goals

**Goals:** exercise replay tail calculation, story-keyed option cache invalidation, per-user key isolation, cache preservation, and cleanup.

**Non-Goals:** construct a `GameLoop`, run SSE generation, or change store behavior.

## Decisions

- Use plain objects as loop placeholders because the store only preserves object identity.
- Force expiration through `last_access` and cleanup interval rather than altering wall-clock functions.

## Risks / Trade-offs

- [In-memory behavior differs after process restart] → persistence restoration remains SessionService integration scope.
