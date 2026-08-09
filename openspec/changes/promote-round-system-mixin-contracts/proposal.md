## Why

Multi-round service orchestration is core gameplay behavior. Its deterministic system-mixin contract is not in the maintained backend gate.

## What Changes

- Promote `tests/test_system_mixin_contract.py` into both maintained backend workflows.

## Capabilities

### New Capabilities

- `round-system-mixin-gate`: Maintained coverage validates round-service initialization and delegation contracts.

### Modified Capabilities

- `test-gates`: The maintained gate includes round system-mixin contracts.

## Impact

- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
