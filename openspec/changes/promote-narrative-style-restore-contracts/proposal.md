## Why

The maintained backend gate needs a deterministic field-compatibility contract
for restoring `narrative_style_id` from persisted game state. The existing
suite exercises `GameLoop.load_game` state restoration and legacy missing/null
field behavior without a provider or mock framework.

## What Changes

- Add `tests/test_narrative_style_restore_contract.py` to both maintained
  backend workflow selections in identical order.
- Record the persistence-field restoration contract and verification criteria.
- Raise the maintained coverage threshold to 51% only if a complete exact
  maintained run succeeds at that threshold.

## Capabilities

### New Capabilities
- `narrative-style-restore-contract-gate`: Maintained regression protection for
  loading narrative-style fields from new, missing, null, and empty persisted
  state values.

### Modified Capabilities

- None.

## Impact

- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
- Existing `tests/test_narrative_style_restore_contract.py` is promoted without
  changing assertions or application code.
