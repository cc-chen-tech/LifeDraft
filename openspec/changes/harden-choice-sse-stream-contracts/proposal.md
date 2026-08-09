## Why

Choice SSE is a browser-visible gameplay state transition, but its replay and
terminal-error behavior can fail deterministically before a browser starts.

## What Changes

- Add provider-free contracts for successful choice streaming, cached replay,
  and data-error cleanup.
- Add the focused contract to the shared maintained backend runner.

## Capabilities

### New Capabilities
- `choice-sse-stream-contracts`: Maintained contracts for choice SSE ordering,
  replay, and terminal errors.

### Modified Capabilities
- None.

## Impact

Tests and the maintained test manifest change; production SSE behavior does
not.
