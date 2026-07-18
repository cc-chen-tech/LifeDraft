## Why

The active image facade has a large maintained coverage gap despite being the
boundary that returns stored images and character context to gameplay routes.
Provider-free database contracts can cover these field and ownership-adjacent
branches without generating media.

## What Changes

- Add real SQLite and local-storage contracts for image facade queries and
  character context normalization.
- Register the contract module in both maintained backend workflows.

## Capabilities

### New Capabilities
- `image-facade-db-contract-coverage`: Maintained real-database coverage for image facade query and context behavior.

### Modified Capabilities

- None.

## Impact

- Adds tests for `src/services/image/__init__.py` only.
- Does not call image providers or change image production behavior.
