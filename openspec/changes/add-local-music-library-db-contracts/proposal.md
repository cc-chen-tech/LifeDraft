## Why

The local AI music library decides whether a generated track can be reused across games, but its maintained coverage only exercises helper functions. The DB-backed index, rejection, and reuse paths can regress without being caught by the stable gate.

## What Changes

- Add provider-free SQLite contract tests for local AI music library indexing and updates.
- Cover deterministic match rejection reasons and reusable-track metadata without route or environment setup.
- Register the new contract test in both maintained backend workflow lists.

## Capabilities

### New Capabilities
- `local-music-library-db-contracts`: Stable persistence and matching contracts for reusable generated music assets.

### Modified Capabilities

- None.

## Impact

- Adds a test module under `tests/` and one matching entry to each backend maintained-gate workflow.
- Exercises `src/services/local_ai_music_library.py` with a disposable SQLite database and local temporary audio files.
