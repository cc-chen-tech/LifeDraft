## Why

The sound queue is part of a user's active game state. The saved-game isolation work proved `/saves` and `GET /api/games/{id}` must not leak another user's game, but the music playlist routes still accepted only `game_id`. That let unauthenticated or wrong-user callers read, mutate, advance, or enqueue music for someone else's game if they knew the id.

## What Changes

- Require authentication for music playlist state routes.
- Verify `games.user_id` before reading, updating, syncing, advancing, or enqueueing generated music.
- Return not-found for wrong-user game ids so playlist state does not reveal another user's save.
- Update MiniMax music route tests to use an owner-authenticated game, matching production browser requests.

## Capabilities

### Modified Capabilities
- `private-id-auth-contract`: Add owner isolation for game music playlist and generated music enqueue routes.

## Impact

- Backend music playlist API routes.
- Generated music API routes that insert tracks into the playlist queue.
- Real DB/API regression tests and MiniMax music contract tests.
