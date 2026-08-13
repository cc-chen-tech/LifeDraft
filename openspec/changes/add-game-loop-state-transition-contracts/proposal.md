## Why

GameLoop state transitions are high-risk gameplay behavior but lack maintained no-mock coverage for resource decay and persisted-event cleanup.

## What Changes

- Add deterministic GameLoop state-transition contracts to both maintained workflows.

## Capabilities

### New Capabilities
- `game-loop-state-transition-maintained-gate`: Require local weekly state-transition contracts in the maintained backend suite.

### Modified Capabilities

- None.

## Impact

Adds one test file and workflow entries only.
