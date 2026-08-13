## Why

Monthly and yearly summaries convert persistent player state into user-visible historical records, but their stable contract tests are not part of the maintained backend gate. A regression in state deltas, prompt context, or provider-failure fallback could therefore pass the fast CI path.

## What Changes

- Add the existing deterministic monthly summary contract suite to both maintained backend workflows.
- Add the existing deterministic yearly summary contract suite to both maintained backend workflows.
- Keep the backend test and coverage workflow selections ordered identically.
- Preserve the current 44 percent maintained coverage threshold until the expanded selection has been measured.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `test-gates`: The maintained backend gate covers monthly and yearly summary state, prompt, and provider-failure contracts.

## Impact

- Affects `.github/workflows/backend-tests.yml` and `.github/workflows/coverage.yml` only.
- Uses existing provider-free tests in `tests/test_monthly_summary_contract.py` and `tests/test_yearly_summary_contract.py`.
- Does not change production code, APIs, database schema, or frontend behavior.
