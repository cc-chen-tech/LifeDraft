# Story Setting Authority Debugging

## Incident

A live game requested a modern urban investigative journalist story, but gameplay entered a North Song / Di Renjie-style ancient template. The UI had accepted a modern world setting, so the visible creation state and gameplay authority state diverged.

## Root Cause

The world-step accept handler wrote the accepted world into the frontend store, then immediately created the backend game with the stale `characterSettings` value captured before that update. The first `/api/games` request could omit `character_settings.world`.

The backend also auto-matched `narrative_style_id` and passed it to the games table metadata, but did not write it into `initial_state`. A loaded `GameLoop` therefore did not have the same style authority as the game row.

## Fix

- Frontend creation now builds an accepted settings snapshot and uses it for initial game creation.
- Backend initialization now writes auto-matched `narrative_style_id` into `initial_state` before saving and loading the game loop.

## Regression Tests

- `frontend/src/__tests__/hooks/useCharacterCreation.test.ts`
  - Covers accepted world content appearing in the initial `/api/games` payload.
- `tests/test_style_matcher.py`
  - Covers auto-matched style being present in saved initial state and the loaded `GameLoop`.

## Operational Checks

If this bug appears again, inspect these first:

1. Browser network payload for `POST /api/games`: `character_settings.world` must match the accepted world shown in creation UI.
2. Backend create-game logs: auto-matched style should be present in both `narrative_style_id` metadata and `initial_state`.
3. Game recovery logs: `GameLoop` should restore the same `narrative_style_id` instead of falling back to a default ancient style.
