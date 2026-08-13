## Why

SSE reconnection after a completed round is a user-visible recovery path. The
maintained gate covers event formatting but does not prove that a reconnecting
subscriber receives only unseen chunks and the terminal event.

## What Changes

- Add provider-free replay contracts using the real durable operation object.
- Add the verified contract file to both maintained workflow selections.
- Raise the coverage floor only when two complete gate runs support it.

## Capabilities

### New Capabilities
- `sse-completed-replay-contract-coverage`: Deterministic completed-operation
  replay coverage for reconnecting SSE subscribers.

### Modified Capabilities
- `test-gates`: The maintained workflows include completed SSE replay contracts.

## Impact

- Affected source under test: `src/api/routers/gameplay/sse_helpers.py`.
- No production behavior, provider dependency, or existing test is changed.
