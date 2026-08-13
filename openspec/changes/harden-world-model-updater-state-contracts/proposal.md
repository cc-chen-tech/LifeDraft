## Why

World-model updater state transitions are high-risk gameplay persistence logic, but existing broad tests use mocks and cannot be maintained gate evidence.

## What Changes

- Add deterministic no-double contracts for location, career, commitment, and causal updates.

## Capabilities

### New Capabilities
- `world-model-updater-state-contract-coverage`: Maintained real-state coverage for pure updater transitions.

### Modified Capabilities
- `test-gates`: Maintained selections include verified updater state contracts symmetrically.

## Impact

- Test-only, workflow, and OpenSpec artifacts.
