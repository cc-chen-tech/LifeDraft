## Why

Round-event SSE connections subscribe to a durable background operation. Existing
tests exercise worker sharing, but do not assert the exact terminal wire protocol
for reconnects, failed workers, and conflicting generation ownership.

## What Changes

- Add deterministic, provider-free contracts for terminal round-event SSE frames.
- Cover replay cursor behavior, worker failure, and generation conflict frames.
- Include the new contract suite in the maintained backend test manifest.

## Capabilities

### New Capabilities
- `round-event-sse-terminal-contracts`: Stable terminal and reconnect semantics
  for the round-event SSE subscriber protocol.

### Modified Capabilities
- None.

## Impact

- New backend tests under `tests/`.
- Maintained test manifest update only; no production code or existing tests are
  modified.
