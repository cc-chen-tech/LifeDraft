## Why

ImageStorageService remains lightly covered in the maintained backend gate even
though local storage compatibility is a user-facing persistence boundary. The
existing unit suite relies on patching, so its coverage cannot be promoted
under the maintained gate's no-mock rule.

## What Changes

- Add deterministic local-file-system contracts for relative and legacy absolute
  paths, API URL encoding, binary retrieval, existence checks, deletion, and
  content hashes.
- Promote the new no-mock suite to both ordered maintained backend workflows
  after verification.

## Capabilities

### New Capabilities

- `image-storage-local-path-contract-gate`: Maintained coverage for local image
  storage compatibility and file lifecycle behavior.

### Modified Capabilities

- None.

## Impact

- `tests/test_image_storage_local_path_contracts.py`
- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
