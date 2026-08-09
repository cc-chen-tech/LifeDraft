## Why

The event-generation coordinator is the concurrency boundary that prevents duplicate producers and controls replay after completed or failed operations. Its deterministic ownership contract suite is not currently included in the maintained backend gate, so these regressions can bypass fast CI.

## What Changes

- Add the existing event-generation ownership contract suite to both maintained backend workflows.
- Keep the two workflow selections ordered identically.
- Retain the current coverage threshold unless the expanded suite reaches the next supported integer floor.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `test-gates`: The maintained backend gate covers event-generation ownership, replay, failure, and SSE-error framing contracts.

## Impact

- Affects only `.github/workflows/backend-tests.yml` and `.github/workflows/coverage.yml`.
- Uses `tests/test_event_generation_contract.py`, which runs entirely in-process.
- Does not change production code, APIs, database schema, or frontend behavior.
