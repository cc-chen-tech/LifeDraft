## Why

Session restoration must distinguish a missing persisted scene image from a valid stored image. This real DB and filesystem behavior lacks maintained coverage.

## What Changes

- Add deterministic session scene-storage contracts to both maintained backend workflows.

## Capabilities

### New Capabilities

- `session-scene-storage-gate`: Maintained coverage validates persisted scene-image restoration checks.

### Modified Capabilities

- `test-gates`: The maintained gate includes real session scene-storage contracts.

## Impact

- `tests/test_session_service_scene_storage_contracts.py`
- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
