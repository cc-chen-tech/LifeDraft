## Why

Game creation accepts generated wealth and relationships payloads from more
than one frontend/API shape. The maintained gate currently covers only a
mock-backed happy path, leaving numeric coercion, bounded amounts, fallback
values, and malformed relationship payloads unprotected.

## What Changes

- Add no-mock contracts for generated initial wealth coercion and key
  precedence.
- Add contracts for canonical relationship payload normalization and required
  game-creation inputs.
- Add the new suite to both ordered maintained backend workflow lists.

## Capabilities

### New Capabilities
- `game-initializer-input-contracts`: Deterministic contracts for normalized
  game-creation settings before persistence or game-loop construction.

### Modified Capabilities

None.

## Impact

- Adds `tests/test_game_initializer_input_contracts.py`.
- Updates the two backend workflow test lists only.
- Does not change production behavior, persistence, or dependencies.
