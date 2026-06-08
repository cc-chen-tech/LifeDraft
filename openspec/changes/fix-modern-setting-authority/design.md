## Root Cause

The failure had two parts:

1. On the world creation step, `handleAcceptAndNext` updated Zustand with the accepted `generatedContent`, but immediately created the game using the stale `characterSettings` value captured by the React hook closure. The first game creation request could therefore omit the accepted modern `world`.
2. `GameInitializer` auto-matched a narrative style and passed it to `GameDatabase.create_game`, but the same style was not present in `initial_state`. When a game loop was loaded from that initial state, `GameLoop.narrative_style_id` could fall back instead of restoring the style used for creation.

## Design

- Build an `acceptedCharacterSettings` snapshot inside `handleAcceptAndNext`.
- Use that snapshot for `/api/games` creation and the `AUTO_ADVANCE_STEPS` completeness check.
- After backend style auto-match completes, write `initial_state["narrative_style_id"] = style_id` before saving and loading `GameLoop`.

## Non-goals

- Rewriting the style matcher scoring model.
- Changing character setting generation prompts.
- Adding a database migration.
