## 1. Regression Coverage

- [x] 1.1 Add a no-mock FastAPI/DB test proving `GET /api/games` returns only the authenticated user's saved games after real save/read setup.
- [x] 1.2 Add a no-mock FastAPI/DB test proving `GET /api/games/{game_id}` rejects a game owned by another user.
- [x] 1.3 Run the new tests before implementation and record that current code already passes the isolation contract.
- [x] 1.4 Add frontend regression tests proving `/saves` does not render stale `savedGames` when the current user is unauthenticated or changes while the page is mounted.

## 2. Implementation

- [x] 2.1 Confirm the current saved-game list and load paths enforce authenticated-user ownership; no production code change was required.
- [x] 2.2 Preserve existing response schemas and frontend `/saves` behavior.
- [x] 2.3 Gate `/saves` rendering through current authentication state and the loaded user id so stale in-memory save lists cannot leak between sessions.

## 3. Verification

- [x] 3.1 Validate the OpenSpec change in strict mode.
- [x] 3.2 Run targeted no-mock tests for saved-game isolation.
- [x] 3.3 Run targeted `/saves` page regression tests.
- [x] 3.4 Run the relevant `./test.sh` layers, including DB/contract coverage.
