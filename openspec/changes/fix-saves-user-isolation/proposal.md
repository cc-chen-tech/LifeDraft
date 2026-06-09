## Why

The 2026-06-08 UX report observed that the saves page could expose games that did not belong to the current player. Save lists are account-private data, so the backend contract needs an explicit no-cross-user guarantee backed by real DB integration coverage.

## What Changes

- Require `GET /api/games` to return only unfinished games owned by the authenticated user.
- Require single-game load paths used from the saves experience to reject games owned by another user.
- Add no-mock regression coverage with real database records for two users and saved game states.
- Keep backend ownership enforcement authoritative while ensuring `/saves` never renders stale client-side save arrays when the current session is unauthenticated or unresolved.

## Capabilities

### New Capabilities

### Modified Capabilities
- `private-id-auth-contract`: Add saved-game isolation requirements for authenticated save listing and loading.

## Impact

- Backend API contract for `GET /api/games` and `GET /api/games/{game_id}`.
- Database repository save/list/load paths involving `games.user_id`.
- Contract and real DB integration tests included in `./test.sh`.
