## Why

HarnessMetrics persists generation-quality evidence used for diagnosis and
release health, but its SQLite lifecycle and aggregation queries have only
minimal maintained coverage.

## What Changes

- Add no-mock, isolated SQLite contracts for generation recording, detailed
  check aggregation, retry distribution, failure patterns, and text reports.
- Add the new suite to both maintained backend workflows.

## Capabilities

### New Capabilities

- `harness-metrics-db-contract-gate`: Maintained database contracts for quality
  metric persistence and deterministic reporting.

### Modified Capabilities

- None.

## Impact

- `tests/test_harness_metrics_db_contracts.py`
- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
