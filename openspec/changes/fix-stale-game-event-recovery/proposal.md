## Why

Production logs showed stale play-page sessions repeatedly requesting `/api/games/{id}/event` after the saved `gameId` no longer existed or no longer belonged to the current user. The event endpoint is valid, but it should never be used as recovery for a confirmed 404 game session.

## What Changes

- Treat 404/not-found failures during initial play-page `syncState()` as terminal stale-session recovery.
- Clear the local game session and return to the home page instead of starting a new event stream for the invalid game id.
- Skip active-game recovery after this explicit stale-session redirect so the play page does not issue extra recovery requests during navigation.
- Add a hook regression test proving stale `gameId` recovery does not call `/event` or `/games/active`.

## Impact

- Frontend session recovery only.
- No API or database schema changes.
