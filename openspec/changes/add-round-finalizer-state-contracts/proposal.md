## Why

Round finalization owns weekly summaries and periodic state bookkeeping, but
its maintained coverage is low because the existing tests use mocks and focus
on asynchronous enrichment. Deterministic state-level contracts can protect
the user-visible summary and history behavior without exercising background
extractors.

## What Changes

- Add no-mock contracts for weekly summary, round information, story
  compression delegation, state decay, and periodic summary bookkeeping.
- Add the suite to both ordered maintained backend workflow lists.

## Capabilities

### New Capabilities
- `round-finalizer-state-contracts`: Maintained contracts for synchronous
  round-finalization state behavior and provider-free degradation.

### Modified Capabilities

None.

## Impact

- Adds `tests/test_round_finalizer_state_contracts.py`.
- Updates only maintained backend workflow lists and OpenSpec artifacts.
- Leaves production behavior and asynchronous enrichment unchanged.
