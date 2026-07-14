## Why

Relationship event definitions encode user-visible thresholds and era-specific labels. Their deterministic no-mock contract is outside the maintained backend gate.

## What Changes

- Promote `tests/test_relationship_events_contract.py` into both maintained backend workflows.

## Capabilities

### New Capabilities

- `relationship-events-gate`: Maintained coverage validates relationship event definitions and lookups.

### Modified Capabilities

- `test-gates`: The maintained gate includes relationship event contracts.

## Impact

- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
