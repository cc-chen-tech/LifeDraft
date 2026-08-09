## Why

Image tests primarily verify provider classification or mocked method presence.
The scene service boundary still needs a deterministic proof that local delivery
creates a durable record and that provider failure leaves no partial scene row.

## What Changes

- Add real SQLite and temporary-storage contracts for scene image creation.
- Add a provider-failure rollback contract that preserves typed failure metadata.
- Add the new suite to the maintained backend test manifest.

## Capabilities

### New Capabilities
- `image-service-db-failure-contracts`: Durable local delivery and no-partial-
  write behavior at the scene image service boundary.

### Modified Capabilities
- None.

## Impact

- New backend tests under `tests/`.
- Maintained test manifest update only; no provider call or production behavior
  changes.
