## 1. Regression Coverage

- [x] 1.1 Add a no-mock FastAPI/DB test proving `GET /api/games` returns only the authenticated user's saved games after real save/read setup.
- [x] 1.2 Add a no-mock FastAPI/DB test proving `GET /api/games/{game_id}` rejects a game owned by another user.
- [x] 1.3 Run the new tests before implementation and record that current code already passes the isolation contract.

## 2. Implementation

- [x] 2.1 Confirm the current saved-game list and load paths enforce authenticated-user ownership; no production code change was required.
- [x] 2.2 Preserve existing response schemas and frontend `/saves` behavior.

## 3. Verification

- [x] 3.1 Validate the OpenSpec change in strict mode.
- [x] 3.2 Run targeted no-mock tests for saved-game isolation.
- [x] 3.3 Run the relevant `./test.sh` layers, including DB/contract coverage.
