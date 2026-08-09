## Why

SSE helper coverage is low despite being a user-facing gameplay protocol.
Several deterministic protocol functions can be tested without starting worker
threads, mutating the environment, connecting to a database, or calling an AI
provider.

## What Changes

- Add pure contract tests for SSE serialization, retry cache clearing,
  generation-key identity, terminal error emission, and completed-event replay.
- Add the new suite to both maintained backend workflow selections in identical
  order after direct and complete-gate verification.

## Capabilities

### New Capabilities
- `sse-protocol-pure-contract-gate`: Maintained regression coverage for the
  deterministic SSE event protocol and reconnect terminal behavior.

### Modified Capabilities

- None.

## Impact

- `tests/test_sse_protocol_pure_contracts.py`
- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
