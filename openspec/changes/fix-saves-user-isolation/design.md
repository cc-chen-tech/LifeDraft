## Context

Saved games are owned records keyed by `games.user_id`. The current route shape already uses authenticated access, but the report exposed a product-level privacy failure: the saves page must never show another player as the active user's game. Existing route tests rely heavily on mocked database/auth layers, which does not prove the save-list query and load path enforce ownership against persisted records.

## Goals / Non-Goals

**Goals:**
- Prove with no-mock tests that a user listing saves sees only that user's games after real DB save/read operations.
- Prove that loading another user's saved game through the public API is rejected.
- Preserve existing response shapes and frontend API usage.

**Non-Goals:**
- Redesign authentication or private ID login.
- Add sharing/public-save discovery behavior.
- Add client-side privacy filtering as a replacement for backend ownership checks.

## Decisions

- Use backend ownership filtering as the authority. Client-side filtering is insufficient because leaked data has already crossed the API boundary.
- Test through FastAPI `TestClient` plus real SQLAlchemy test database fixtures rather than route mocks. This covers producer/consumer fields and the saved DB state path.
- Cover both list and load operations. Hiding another user's save from the list is not enough if the detail endpoint can still load it by id.

## Risks / Trade-offs

- Existing fixtures may have mock-oriented helpers that are faster to use but weaker for this issue. Mitigation: place the regression in the DB/API integration layer and use the same dependency overrides used by other no-mock contract tests.
- The code may already filter correctly. Mitigation: keep the change as a regression-test PR if the red test exposes only missing coverage, and avoid unnecessary production edits.
