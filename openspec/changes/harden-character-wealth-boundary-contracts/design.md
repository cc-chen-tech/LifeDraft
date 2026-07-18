## Context

`update_character_settings` deliberately applies generated opening wealth only before the first played round. Existing tests prove the opening synchronization path, but not the guard that protects persisted gameplay wealth after play begins.

## Goals / Non-Goals

**Goals:**

- Exercise the endpoint contract with a late wealth payload and an already-played state.
- Assert that the settings payload persists while the saved balance and ledger remain unchanged.
- Run the regression in the maintained backend gate.

**Non-Goals:**

- Change router, ledger, schema, or frontend behavior.
- Re-test wealth arithmetic or unrelated character-creation providers.

## Decisions

- Use a focused API contract test with an explicit persisted state. This exercises request validation, merge behavior, and the setup-versus-play guard without requiring external AI services.
- Patch the live session store to return no session. The durable saved state is the boundary under test, and this keeps the test deterministic.
- Preserve an existing ledger in the fixture and assert it is not rewritten. Checking only `wealth` would miss a destructive opening-balance reset.

## Risks / Trade-offs

- [Mocked persistence facade differs from repository storage] -> The assertion targets the endpoint's semantic input to `save_game_progress`; separate repository tests already cover storage round trips.
- [Future legitimate rebalancing behavior] -> The scenario is constrained to a late character-settings payload after a recorded round, not general gameplay wealth updates.
