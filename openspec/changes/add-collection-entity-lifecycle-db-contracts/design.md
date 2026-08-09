## Context

The maintained collection tests verify response shaping and selected removal paths, but lifecycle operations remain vulnerable to regressions in player-state mutation and ORM cleanup. These paths are deterministic with a disposable SQLite database.

## Goals / Non-Goals

**Goals:**
- Verify recognized entities are added once with source metadata preserved.
- Verify collection deletion removes only the linked image record and enforces player protection.
- Keep tests provider-free and isolated from shared database state.

**Non-Goals:**
- Generate images, call collection routes, or test recognition model output.
- Change production collection semantics.

## Decisions

- Use a new in-memory SQLite engine per test and real `Game`/`Image` records.
- Use `PlayerState` as the state authority, asserting both its mutations and persisted image cleanup.
- Test service exceptions rather than HTTP status mappings because route behavior is out of scope.
- Register the test immediately after existing collection DB contracts in both workflow lists.

## Risks / Trade-offs

- [In-memory SQLite does not represent all deployment DB behavior] -> Assertions target service state transitions and ORM filters.
- [Recognition payload is permissive] -> Use duplicate and player-name inputs to lock the intended deduplication boundary.
