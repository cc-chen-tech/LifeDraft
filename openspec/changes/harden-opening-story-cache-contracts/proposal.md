## Why

Opening-story SSE cache behavior protects users from duplicate generation and makes a finished story immediately replayable after reconnect. These browser-visible branches are deterministic but not covered by the maintained backend suite.

## What Changes

- Add provider-free contracts for cached opening-story SSE frames and duplicate-generation rejection.
- Add deterministic truncation-boundary contracts.
- Register the test module in both maintained backend workflow lists.

## Capabilities

### New Capabilities

- `opening-story-cache-contracts`: Maintained contracts for opening-story cache, duplicate-request, and truncation semantics.

### Modified Capabilities

- None.

## Impact

Only tests and workflow test lists change. The covered code is `src/api/routers/character.py`; no model call or production behavior changes.
