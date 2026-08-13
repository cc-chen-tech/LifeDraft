## Why

The maintained backend gate exercises only 15.38% of `RoundChoiceProcessor`,
despite this component owning resource clamping and choice wealth transactions.
These state transitions are user-visible and can be tested deterministically
without an AI provider, database, or mock framework.

## What Changes

- Add no-mock contract tests for bounded choice effects at resource limits.
- Add no-mock contract tests for idempotent choice wealth transactions and
  invalid wealth input normalization.
- Add the new focused test file to the maintained backend and coverage gates.
- Raise the maintained coverage floor only when two complete gate runs prove a
  higher value.

## Capabilities

### New Capabilities
- `choice-processor-state-contract-coverage`: Deterministic coverage of choice
  resource and wealth state transitions.

### Modified Capabilities
- `test-gates`: The maintained backend selection includes the verified choice
  processor state contract tests.

## Impact

- Affected source under test: `src/game/round/choice_processor.py`.
- Affected gates: `.github/workflows/backend-tests.yml` and
  `.github/workflows/coverage.yml`.
- No production behavior, API contract, or existing test is changed.
