## Why

Reloading during event generation must preserve the saved story and produce fallback choices if the options request times out. The deterministic recovery suite covers this user-visible continuity path but is outside the maintained backend gate.

## What Changes

- Add the existing current-event recovery contract suite to both maintained backend workflows.
- Preserve exact workflow-list parity and raise the floor only when full-suite measurement supports it.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `test-gates`: The maintained backend gate covers saved current-event restoration and options-timeout fallback.

## Impact
- Promotes `tests/test_game_loop_current_event_restore.py` only; no production code or existing test changes.
