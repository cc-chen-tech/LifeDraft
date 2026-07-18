## Why

Music playback state is a browser-visible workflow, yet the maintained suite
does not gate the queue policy or its persistent transitions. Regressions can
interrupt the current song, duplicate title variants, lose generated tracks, or
desynchronize playback state before browser tests expose them.

## What Changes

- Add provider-free queue policy tests for title-family deduplication and
  generated-track priority.
- Add real SQLite service tests for merge, playback sync, advance, and queue
  wraparound state transitions.
- Register the new module in both maintained backend workflows.

## Capabilities

### New Capabilities

- `music-playlist-state-contracts`: Maintained contracts for stable playlist
  queue policy and persisted playback transitions.

### Modified Capabilities

- None.

## Impact

Adds tests and maintained workflow entries only. Production playlist code,
existing music tests, API routes, and provider behavior remain unchanged.
