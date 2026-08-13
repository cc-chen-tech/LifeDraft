## Why

Language detection determines the GameLoop recovery language. Its complete deterministic contract is not maintained.

## What Changes

- Promote `tests/test_language_contract.py` into both maintained backend workflows.

## Capabilities

### New Capabilities

- `language-detection-gate`: Maintained coverage validates state-based language detection.

### Modified Capabilities

- `test-gates`: The maintained gate includes language detection contracts.

## Impact

- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
