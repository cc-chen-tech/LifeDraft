## Why

SSE connection limits, resumed terminal views, and Last-Event-ID parsing are provider-free gameplay safety boundaries. Their deterministic contract exists but is absent from the maintained backend gate.

## What Changes

- Promote the existing gameplay event protocol contract into both maintained backend workflows.

## Capabilities

### New Capabilities

- `gameplay-event-protocol-gate`: Maintained coverage protects SSE capacity, resume-view, and cursor protocol behavior.

### Modified Capabilities

- `test-gates`: The maintained backend gate includes deterministic gameplay event protocol contracts.

## Impact

- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
