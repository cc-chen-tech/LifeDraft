## Why

Choice SSE drives the gameplay interaction after a player commits an option. Its callback, replay, completion, and error semantics are browser-visible but have limited maintained coverage without mock-heavy tests.

## What Changes

- Add provider-free contracts for successful choice streaming, cached replay, and data-error cleanup.
- Register the focused module in both maintained backend workflows.

## Capabilities

### New Capabilities

- `choice-sse-stream-contracts`: Maintained contracts for choice SSE ordering, replay, and terminal error behavior.

### Modified Capabilities

- None.

## Impact

Only `src/api/routers/gameplay/sse_helpers.py` coverage and workflow test lists change. No production SSE behavior changes.
