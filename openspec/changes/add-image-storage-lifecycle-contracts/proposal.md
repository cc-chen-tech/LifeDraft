## Why

Local image storage persists generated assets and recovery uploads, but the maintained backend gate does not cover save-time filenames, compression fallback, and the resulting read lifecycle.

## What Changes

- Add real local image-storage save lifecycle contracts to both maintained backend workflows.

## Capabilities

### New Capabilities

- `image-storage-lifecycle-maintained-gate`: Require maintained provider-free contracts for locally persisted image assets.

### Modified Capabilities

- None.

## Impact

Adds one test file and workflow entries only.
