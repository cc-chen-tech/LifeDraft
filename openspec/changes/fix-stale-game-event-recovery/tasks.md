## 1. Reproduce

- [x] Add a failing hook test for an initial play-page `syncState()` 404 from a stale `gameId`.

## 2. Fix

- [x] Detect not-found initial sync failures in `usePlayGame`.
- [x] Clear local game state and redirect home without starting `/api/games/{id}/event`.
- [x] Prevent a follow-up `/api/games/active` request during the stale-session redirect.

## 3. Verify

- [x] Run the targeted stale-game hook test red, then green.
- [x] Run full `usePlayGame` hook tests.
- [x] Run `openspec validate fix-stale-game-event-recovery --strict`.
- [x] Run `./test.sh preflight`.
