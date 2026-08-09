## Why

Choice processing mutates player state, derives character effects, and returns
fallback text when an AI result is unavailable. The maintained suite covers a
narrow happy path but leaves negative relationships, context, invalid indices,
and deterministic fallback behavior unguarded.

## What Changes

- Add no-mock contracts for relationship-effect derivation and character
  context.
- Add deterministic contracts for invalid choices and result-text fallback
  paths.
- Add the suite to both maintained backend workflow lists.

## Capabilities

### New Capabilities
- `decision-effect-fallback-contracts`: Maintained decision-processing
  contracts for state effects and provider-free degradation.

### Modified Capabilities

None.

## Impact

- Adds `tests/test_decision_effect_fallback_contracts.py`.
- Updates the two maintained backend workflow lists only.
- Does not change production state transitions or provider behavior.
