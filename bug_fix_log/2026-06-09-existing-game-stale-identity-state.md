# 2026-06-09 Existing Game Stale Identity State

## Summary

Production browser QA on `story101.live` found a severe state consistency failure after creating a fresh character:

- Created character: `沈若澜`
- Requested setting: 2026 Shenzhen, female AI education product founder, 80000 RMB startup funds
- Production play route: `https://story101.live/play`
- Actual first playable event: stale `苏清岚`, 2024 Shanghai, independent game producer

Evidence:

- Screenshot: `docs/screenshots-2026-06-09-heartbeat-1532/play-initial.png`
- Browser localStorage snapshot showed `gameId=109` and `character_settings` for `沈若澜`, but top-level `player_name` and `life_vision` still contained stale `苏清岚` / 2024 Shanghai values.

## Root Cause

The create flow can create a game record before portrait/background generation is complete. When the user later starts the game and `gameId` already exists, the frontend only called:

- `PATCH /api/games/{game_id}/character-settings`

That endpoint persisted late `character_settings` and wealth, but it did not accept or overwrite top-level `player_name` and `life_vision`.

Gameplay event generation reads those top-level fields, so a reused existing game could combine new character settings with stale protagonist identity and story premise.

## Regression Tests

- `tests/test_character_settings_api_contract.py::TestCharacterSettingsUpdateAPIContract::test_update_character_settings_can_replace_stale_identity_before_play`
- `frontend/src/__tests__/hooks/useCharacterCreation.test.tsx` equivalent coverage in `frontend/src/__tests__/hooks/useCharacterCreation.test.ts`:
  - `patches existing game identity when gameId already exists`

The backend test failed before the fix with saved `player_name == "苏清岚"` after patching a new `沈若澜` character.

## Fix

- `src/api/schemas.py`
  - Added optional `player_name` and `life_vision` to `UpdateCharacterSettingsRequest`.
- `src/api/routers/games.py`
  - Persists non-empty replacement `player_name`.
  - Persists replacement `life_vision`.
  - Mirrors both fields into any active in-memory game session.
- `frontend/src/lib/api.ts`
  - Allows `patchCharacterSettings` callers to include identity fields.
- `frontend/src/hooks/useCharacterCreation.ts`
  - Sends `player_name` and `life_vision` when starting a game with an existing `gameId`.

## Verification

- `pytest tests/test_character_settings_api_contract.py -q`
- `npx jest src/__tests__/hooks/useCharacterCreation.test.ts --runInBand --no-cache`

Status: fixed locally, pending broader gate and deploy.
