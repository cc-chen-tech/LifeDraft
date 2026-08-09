## Why

Active-game recovery must never restore another user's save, even if a stale
or previously written `last_active_game_id` references it. The repository has
the defensive lookup behavior, but the maintained suite does not prove it
against the real database or that it persists its self-healing cleanup.

## What Changes

- Add a real-database contract for cross-user active-game pointer recovery.
- Verify rejected pointers are cleared durably after lookup.
- Register the regression in the shared maintained backend manifest.

## Capabilities

### New Capabilities
- `active-game-owner-recovery-db`: Real database ownership and self-healing
  contracts for active-game recovery.

### Modified Capabilities

- None.

## Impact

This change adds a provider-free database integration test and one maintained
test manifest entry. Production session recovery behavior is unchanged.
