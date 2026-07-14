## Why

Scheduled-event unit contracts cover the domain state machine, but the deterministic flow suite additionally verifies PlayerState and Commitment integration. Without it, a regression in how commitments become player-visible scheduled events can bypass the maintained gate.

## What Changes

- Add the existing scheduled-event flow suite to both maintained backend workflows.
- Preserve ordered workflow-list parity and retain the current coverage floor unless measurement supports a higher one.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `test-gates`: The maintained backend gate covers scheduled events through PlayerState and Commitment integration boundaries.

## Impact

- Affects only the maintained workflow lists.
- Promotes `tests/test_scheduled_events.py` without changing production code or existing tests.
