## Why

Image storage is a low-coverage persistence boundary. Its deterministic real-filesystem compression contract is excluded from the maintained backend gate.

## What Changes

- Promote the existing image storage compression contract into both maintained backend workflows.

## Capabilities

### New Capabilities

- `image-storage-compression-gate`: Maintained coverage validates persisted image compression and retrieval.

### Modified Capabilities

- `test-gates`: The maintained backend gate includes deterministic image storage compression coverage.

## Impact

- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
