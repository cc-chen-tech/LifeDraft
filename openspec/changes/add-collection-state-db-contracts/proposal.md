## Why

Collection state mutations combine user-visible inventory changes with deletion
of persisted image records. Existing coverage concentrates on shapes and mocked
routes, leaving these consistency and permission branches weakly protected.

## What Changes

- Add no-mock tests for manual item creation and regeneration permission rules.
- Add real SQLite tests that delete URL-encoded item and landmark names and
  verify both PlayerState and linked Image records are removed.
- Promote the deterministic suite into both maintained backend workflows after
  direct and complete-gate verification.

## Capabilities

### New Capabilities
- `collection-state-db-contract-gate`: Maintained contracts for collection
  mutation, permission, and state/database consistency.

### Modified Capabilities

- None.

## Impact

- `tests/test_collection_state_db_contracts.py`
- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
