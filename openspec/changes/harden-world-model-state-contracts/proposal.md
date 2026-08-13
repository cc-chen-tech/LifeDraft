## Why

World-model updates determine which promises and consequences remain available to later story generation. Existing causal-chain coverage calls a removed method and can pass without exercising the live lifecycle, leaving retention and serialization regressions undetected.

## What Changes

- Add no-mock state-contract tests for causal-chain creation, resolution, persistence, and retention expiry.
- Add a regression test for commitment cleanup that preserves pending commitments while expiring old resolved entries.
- Include the new tests in the maintained backend test manifest.

## Capabilities

### New Capabilities

- `world-model-lifecycle-contracts`: Regression coverage for durable causal-chain and commitment lifecycle semantics.

### Modified Capabilities

- None.

## Impact

- Adds focused tests around `src.game.world_model_updater.WorldModelUpdater` and `PlayerState` serialization.
- Adds one maintained-backend manifest entry.
