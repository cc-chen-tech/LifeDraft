## Why

Live gameplay showed a high-severity setting-authority failure: a player requested a modern urban female investigative journalist story, but the generated game entered a North Song / Di Renjie-style ancient template. The creation UI had accepted a modern world setting, while the backend initialized gameplay from stale or incomplete character settings and did not persist the auto-matched narrative style into the first recoverable game state.

## What Changes

- Ensure the world setting accepted on the creation step is included in the first `/api/games` creation request.
- Ensure an auto-matched `narrative_style_id` is written into the initial session state, not only the games table metadata.
- Add regression coverage for the frontend creation request and backend initializer recovery state.
- Document the root cause, reproduction, and regression guards.

## Impact

- Frontend character creation hook.
- Backend `GameInitializer` initial state contract.
- Style matcher / initializer tests.
- No schema migration is required.
