## Why

Save points are the durable boundary for player rewind and resume. The repository
has little maintained behavior coverage, leaving ownership and snapshot
visibility regressions to surface late in interactive testing.

## What Changes

- Add real SQLite save-point lifecycle and ownership contracts.
- Register the contract module in both maintained backend workflows.

## Capabilities

### New Capabilities
- `save-point-repository-db-contract-coverage`: Maintained real-database contracts for save-point lifecycle semantics.

### Modified Capabilities

- None.

## Impact

- Adds provider-free tests for `src/database/save_point_repository.py`.
- Covers save, list, load, delete, and timeline metadata through the repository API.
