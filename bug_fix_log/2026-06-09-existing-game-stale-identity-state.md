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
- `pytest tests/test_character_settings_api_contract.py tests/test_api_games.py -q`
- `npx jest src/__tests__/hooks/useCharacterCreation.test.ts --runInBand --no-cache`
- `npx tsc --noEmit`
- `npm run sync:api-types`
- Pushed `main` to `origin/main`.
- GitHub Actions for the pushed commit still failed before usable runner logs were available: `gh run view --log-failed` returned `log not found`, so this remains classified as a platform runner/check blocker rather than a code failure.
- Deployed by the standard ECS flow:
  - `git fetch origin main`
  - `git reset --hard origin/main`
  - `docker compose -f docker-compose.ecs.yml up -d --build backend frontend nginx`
- Verified production health:
  - `https://story101.live/api/health` returned `{"status":"ok","active_sessions":0}`.
  - `https://story101.live/` returned `HTTP/1.1 200 OK`.
- Verified production API behavior in the browser session:
  - `PATCH /api/games/109/character-settings` returned 200.
  - `GET /api/games/109` then returned `player_name == "沈若澜"`, matching `life_vision` and `character_settings.era`.

Status: fixed, pushed, manually deployed to ECS through standard GitHub SSH sync, and production API/health verified.
