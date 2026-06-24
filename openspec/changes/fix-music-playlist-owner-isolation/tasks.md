## 1. Root Cause

- [x] Confirm playlist read/update/sync/advance routes accepted only `game_id`.
- [x] Confirm generated music routes could insert tracks into another user's playlist by `game_id`.
- [x] Reproduce the leak/mutation path with no-mock real DB API tests.

## 2. Fix

- [x] Require authenticated users for playlist state routes.
- [x] Check `games.user_id` before playlist reads and mutations.
- [x] Check `games.user_id` before synchronous and asynchronous generated music enqueue.
- [x] Update MiniMax music contract tests to call playlist/generation routes as the game owner.

## 3. Verify

- [x] Run focused RED tests before implementation.
- [x] Run focused owner-isolation tests after implementation.
- [x] Run related real DB, MiniMax music, and playlist DB tests.
- [x] Run `openspec validate fix-music-playlist-owner-isolation --strict`.
- [x] Run project preflight before commit.
