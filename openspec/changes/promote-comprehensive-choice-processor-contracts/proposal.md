## Why

Round-choice processing remains a high-risk state transition boundary. The comprehensive deterministic contract reaches 90% direct coverage but is absent from the maintained gate.

## What Changes

- Promote `tests/test_choice_processor_contract.py` into both maintained backend workflows.

## Capabilities

### New Capabilities

- `comprehensive-choice-processor-gate`: Maintained coverage protects choice result, resource, wealth, and terminal-view transitions.

### Modified Capabilities

- `test-gates`: The maintained gate includes comprehensive choice processor contracts.

## Impact

- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
