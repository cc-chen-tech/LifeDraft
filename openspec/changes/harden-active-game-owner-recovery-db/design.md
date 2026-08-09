## Context

`SessionRepository.get_active_game` verifies that the active game belongs to
the requesting user and clears invalid pointers. Existing tests cover deleted
games with an in-memory session factory, but not the cross-user case or durable
cleanup in the configured database.

## Goals / Non-Goals

**Goals:**
- Exercise the repository through the real configured database.
- Assert another user's game ID is never returned.
- Assert the invalid pointer is persisted as null after lookup.

**Non-Goals:**
- Alter active-game write behavior or API authentication.
- Exercise browser resume behavior or GameLoop reconstruction.

## Decisions

- Create two uniquely named users and one owned game using the production
  SQLAlchemy models, then seed the stale pointer directly. This models a
  historical corrupt/stale value without weakening the test through mocks.
- Read the user again after repository lookup to assert durable cleanup, not
  merely the immediate return value.
- Clean up created records in a `finally` block to keep the shared local DB
  safe for repeated maintained-gate runs.

## Risks / Trade-offs

- [Shared SQLite schema can be affected by prior tests] -> call `init_db` and
  use unique IDs, matching existing real-DB gate patterns.
- [Direct pointer seed is not a public write path] -> it specifically verifies
  the defensive recovery behavior for stale persisted state.
