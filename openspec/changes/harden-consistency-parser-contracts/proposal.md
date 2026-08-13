## Why

The consistency validator parses AI responses into retry decisions, but its parsing behavior is not maintained without mocks.

## What Changes

- Add deterministic parser contracts and promote them into maintained workflows after verification.

## Capabilities

### New Capabilities
- `consistency-parser-contract-coverage`: Local contracts for consistency response parsing.

### Modified Capabilities
- `test-gates`: Maintained lists include verified consistency parser contracts symmetrically.

## Impact

- Test-only files, workflows, and OpenSpec artifacts.
