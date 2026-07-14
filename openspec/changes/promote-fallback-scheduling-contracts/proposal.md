## Why

Fallback events keep gameplay usable when generation degrades, while scheduled events preserve player commitments across rounds and weeks. Their deterministic, high-coverage contract suites are not in the maintained backend gate, leaving core recovery and scheduling regressions outside fast CI.

## What Changes

- Add existing fallback-event and scheduled-event contract suites to both maintained backend workflows.
- Keep workflow selections ordered identically.
- Retain the 45 percent coverage floor unless the expanded selection proves the next integer threshold.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `test-gates`: The maintained backend gate covers fallback gameplay generation and scheduled-event state transitions.

## Impact

- Affects only the two maintained workflow selection lists.
- Promotes `tests/test_fallback_events_contract.py` and `tests/test_scheduled_events_contract.py`.
- Does not change production code, APIs, persistence schema, or existing tests.
