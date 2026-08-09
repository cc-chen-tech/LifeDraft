## Why

Style-aware validation is the deterministic guard before generated narrative is
accepted, but its detailed evidence and score calculation have negligible
maintained coverage.

## What Changes

- Add no-mock contracts for full style evidence, failed hook detection,
  score weighting, harness adaptation, and no-style fallback.
- Add the suite to both maintained backend workflows after verification.

## Capabilities

### New Capabilities

- `style-validator-contract-gate`: Maintained coverage for pure style
  validation and scoring behavior.

### Modified Capabilities

- None.

## Impact

- `tests/test_style_validator_contracts.py`
- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
