## Why

Image and scene read endpoints translate persisted state into frontend-visible
fields, but their maintained coverage is low. Real database contracts can catch
ownership, soft-delete, and week/stage lookup regressions before browser tests.

## What Changes

- Add real SQLite contracts for image and scene read endpoints.
- Register the contract module in both maintained backend workflows.

## Capabilities

### New Capabilities
- `images-router-read-contract-coverage`: Maintained real-database coverage for image router read semantics.

### Modified Capabilities

- None.

## Impact

- Adds tests for `src/api/routers/images.py` read-only and soft-delete paths.
- Excludes image provider and background generation paths.
