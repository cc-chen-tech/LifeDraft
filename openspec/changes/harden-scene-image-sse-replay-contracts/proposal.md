# Harden Scene Image SSE Replay Contracts

## Why

The scene image frontend subscribes to a replay-style SSE endpoint. Existing tests
cover one cached terminal event at a time, but do not prove that latest events use
the stable game/week/round/stage key or that a game replay excludes another game's
events.

## What Changes

- Add a real database and HTTP contract test for scene image SSE replay.
- Verify latest-event replacement, multi-event replay, field preservation, and
  cross-game isolation.
- Include the contract in the maintained backend test manifest.

## Scope

This change adds tests and test-manifest coverage only. It does not change runtime
code or existing tests.
