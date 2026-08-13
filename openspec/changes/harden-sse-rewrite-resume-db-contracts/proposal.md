## Why

SSE rewrite and generation recovery state are visible gameplay boundaries that
previously required browser-agent diagnosis. A provider-free real database
contract can detect text-loss and resume-view regressions before they reach a
browser.

## What Changes

- Add real SQLite contracts for rewritten current-event persistence.
- Add real SQLite contracts for generation resume-view persistence.
- Register the contract module in both maintained backend workflows.

## Capabilities

### New Capabilities
- `sse-rewrite-resume-db-contract-coverage`: Maintained real-database coverage for SSE-visible persisted state.

### Modified Capabilities

- None.

## Impact

- Adds a test module for `src/api/routers/gameplay/sse_helpers.py`.
- Exercises the existing game-state persistence path without providers, network calls, or mocks.
