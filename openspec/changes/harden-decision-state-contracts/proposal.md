## Why

Choice application changes resources, relationships, a wealth audit ledger, and
decision history. Its maintained coverage is sparse and existing broad tests
mix mock-based result generation with deterministic state behavior.

## What Changes

- Add real-`PlayerState` contracts for deterministic choice application,
  wealth-ledger idempotency, resource bounds, and relationship synchronization.
- Promote only the twice-stable suite to maintained backend workflows.

## Capabilities

### New Capabilities
- `decision-state-contract-coverage`: Deterministic contracts for applying a
  choice to player, character, ledger, and history state.

### Modified Capabilities
- `test-gates`: Maintained workflows run the stable decision state contracts in
  matching order.

## Impact

- Adds tests for `src/game/decisions.py` without production changes.
