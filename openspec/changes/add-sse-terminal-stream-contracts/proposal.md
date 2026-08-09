## Why

The durable SSE operation is the recovery boundary for browser disconnects and
generation failures, yet its terminal replay paths have very low maintained
coverage.

## What Changes

- Add provider-free contracts for completed replay, generation conflicts,
  terminal waiting, and resume-view state.
- Promote the new suite to both maintained backend workflows.

## Capabilities

### New Capabilities

- `sse-terminal-stream-contract-gate`: Maintained contracts for durable
  event-generation stream terminal behavior.

### Modified Capabilities

- None.

## Impact

- `tests/test_sse_terminal_stream_contracts.py`
- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
