## Why

Late character-creation responses can contain an initial-wealth field after a game already has persisted gameplay. The setup endpoint must retain that metadata without treating it as permission to rewrite the player's earned balance.

## What Changes

- Add a regression contract test for the post-play character-settings update boundary.
- Keep the new test in the maintained backend test manifest so this field-semantics regression remains gated.

## Capabilities

### New Capabilities

- `character-wealth-update-boundary`: Regression coverage for preserving post-play wealth while storing late character settings.

### Modified Capabilities

- None.

## Impact

- Adds a backend API contract test for `PATCH /api/games/{game_id}/character-settings`.
- Adds that test file to `scripts/run-maintained-backend-tests.sh`.
