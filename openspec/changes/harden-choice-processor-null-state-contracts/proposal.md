## Why

Choice effect normalization is callable while player state is unavailable during
recovery and initialization paths. Its fallback must preserve caller-owned
input and return no fabricated warning metadata.

## What Changes

- Add no-mock regression contracts for normalization and custom-effect
  delegation without player state.
- Retain the test in the existing maintained choice processor test file.
- Raise the maintained floor only after two complete runs prove the next value.

## Capabilities

### New Capabilities
- `choice-processor-null-state-contract-coverage`: Deterministic fallback
  behavior for unavailable player state.

### Modified Capabilities
- `test-gates`: The maintained choice processor contract file covers the
  unavailable-state branch.

## Impact

- Affected source under test: `src/game/round/choice_processor.py`.
- No production behavior, API contract, or existing test is changed.
