# Design

## Scope

This change only affects the sync fallback endpoints:

- `POST /api/games/{game_id}/choice-sync`
- `POST /api/games/{game_id}/custom-choice-sync`

SSE endpoints still require an active current event and are not made idempotent.

## Behavior

`_restore_current_event_if_needed` already detects the "already processed"
condition when there is no `current_event_data` but saved `round_history` exists.
The sync endpoints will catch that specific condition and reconstruct a normal
choice result from the latest persisted round history entry.

The reconstructed response uses existing frontend-consumed fields:

- `story_continuation`
- `summary`
- `effects_applied`
- `effects_requested`
- `resource_warnings`
- `need_weekly_summary`
- `weekly_summary`
- `game_over`

If the saved history is missing usable story or summary text, the endpoint keeps
the existing error behavior.

## Verification Strategy

Add a real DB integration test that:

1. Creates a real user, game, and latest `GameState` row containing a completed
   round with no current event.
2. Sends an authenticated `POST /api/games/{id}/choice-sync`.
3. Verifies the API returns the persisted result fields with HTTP 200.

The test does not use mocks or skips and will run in `./test.sh all` Layer 4.
