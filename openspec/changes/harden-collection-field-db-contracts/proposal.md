# Harden Collection Field DB Contracts

## Why

Collection responses merge game-state entities with persisted image versions. The
important regressions are field drift, stale image selection, and cross-game data
leakage, none of which require a browser or image provider to test.

## What Changes

- Add a real DB collection response contract for entity fields and image versions.
- Verify active/latest image selection and cross-game image isolation.
- Add the contract to the maintained backend manifest.
