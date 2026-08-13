## Why

The maintained backend gate omits stable, deterministic contracts for continuity, wealth, and persisted player state even though these paths protect game-history correctness. Promoting them raises meaningful coverage without introducing external providers or mock-driven tests.

## What Changes

- Add the existing continuity-ledger contracts to both maintained backend workflows.
- Add the existing wealth-ledger unit and cross-consumer integration contracts.
- Add the real database player-state submodule persistence contracts.
- Preserve ordered workflow parity and the existing 51% global coverage threshold.

## Capabilities

### New Capabilities
- `ledger-state-maintained-gate`: Require deterministic continuity, wealth, and persisted state contracts in the maintained backend suite.

### Modified Capabilities

- None.

## Impact

Only the maintained-test lists in `.github/workflows/coverage.yml` and `.github/workflows/backend-tests.yml` change. The selected tests exercise local state and the test database; no production code, API behavior, external provider, or browser flow changes.
