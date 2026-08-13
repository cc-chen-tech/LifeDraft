## Why

Image persistence is a user-visible boundary, but the maintained suite covers
mostly local paths and leaves OSS transport behavior unprotected.

## What Changes

- Add deterministic storage transport tests for local and OSS lifecycle paths.
- Register the new module in both maintained backend workflows.

## Capabilities

### New Capabilities
- `image-storage-transport-contracts`: Maintained contracts for image storage
  transport paths, URLs, retrieval, deletion, and existence checks.

### Modified Capabilities

- None.

## Impact

Adds test coverage and workflow entries only; production storage code is unchanged.
