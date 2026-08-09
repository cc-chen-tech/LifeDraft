## Why

Saved gameplay recovery must restore valid events, discard stale events, and preserve recoverable partial events. These provider-free branches are insufficiently covered by the maintained gate.

## What Changes

- Add GameLoop saved-event recovery contracts to both maintained backend workflows.

## Capabilities

### New Capabilities

- `game-loop-load-recovery-gate`: Maintained coverage validates saved current-event recovery behavior.

### Modified Capabilities

- `test-gates`: The maintained gate includes GameLoop load recovery contracts.

## Impact

- `tests/test_game_loop_load_recovery_contracts.py`
- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
