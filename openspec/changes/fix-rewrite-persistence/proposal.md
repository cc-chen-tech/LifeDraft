# Fix Rewrite Persistence

## Why

The inline rewrite UI could show a rewritten story in the current page, but the backend streaming rewrite path only mutated `game_loop.current_event.event_description`. It did not update `player_state.current_event_data` or auto-save the game state. After refresh, save/load, or any server-side consumer that reads the persisted current event, the game could continue from the old story.

The same persistence gap existed in the non-streaming `/api/games/{game_id}/rewrite` path.

## What Changes

- Add a shared backend helper that treats rewrite completion as a current-event mutation.
- Sync `current_event.event_description` and `player_state.current_event_data.event_description`.
- Preserve and update `story_text` when the persisted event snapshot already contains it.
- Auto-save the updated player state after streaming and non-streaming rewrite completion.
- Add regression coverage for streaming and non-streaming rewrite persistence.

## Impact

- Backend story rewrite endpoints only.
- No schema or API response shape changes.
- Existing frontend rewrite UI continues to receive the same `new_story`, `rewritten_story`, and `event` payload.
