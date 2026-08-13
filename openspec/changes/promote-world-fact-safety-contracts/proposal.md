## Why

Generated settings that sound like real legal, economic, or statistical facts
need visible fictional qualification. The existing deterministic no-mock suite
newly covers 11 maintained-uncovered statements in this safety boundary.

## What Changes

- Add `tests/test_world_fact_safety_contract_no_mock.py` to both maintained
  backend workflow selections in identical order.
- Define the factual-qualification and idempotency regression contract.
- Verify selection parity and the full maintained 51% gate.

## Capabilities

### New Capabilities
- `world-fact-safety-contract-gate`: Maintained coverage for visibly qualifying
  real-sounding generated world claims without altering qualitative fiction.

### Modified Capabilities

- None.

## Impact

- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
- Existing `tests/test_world_fact_safety_contract_no_mock.py` is promoted
  unchanged.
