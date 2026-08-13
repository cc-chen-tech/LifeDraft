## Why

Collection lifecycle operations turn recognized story entities into persistent player state and remove their related image records. The maintained gate exercises response shapes but lacks a real-DB contract for these state transitions and ownership safeguards.

## What Changes

- Add provider-free SQLite tests for recognized entity insertion, collection mutation boundaries, and image-record cleanup.
- Verify ownership lookup and protected-player deletion through the real ORM service path.
- Register the new module in both maintained backend workflow lists.

## Capabilities

### New Capabilities
- `collection-entity-lifecycle-db-contracts`: Stable database-backed collection entity and cleanup contracts.

### Modified Capabilities

- None.

## Impact

- Adds one maintained test module and matching workflow entries.
- Covers `src/services/collection_service.py` without providers, routes, mocks, or environment changes.
