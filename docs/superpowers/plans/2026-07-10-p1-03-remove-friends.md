# P1-3 Remove Friends Feature Implementation Plan

**Goal:** Remove the broken friend UI and runtime request API completely, while preserving historical friendship database structures that are outside this product removal.

**Architecture:** Treat friends as a retired product capability. Remove every user-reachable entry and frontend consumer first, unregister and delete the dedicated FastAPI router and schemas, and make the OpenAPI/browser route contracts explicitly assert that all former endpoints are absent. Keep `Friendship` ORM data and `UserManager` helpers because they are not needed to make the retired runtime surface unreachable and may hold historical data.

**Tech Stack:** React 19, Zustand, TypeScript, Jest, Playwright, FastAPI, pytest, generated OpenAPI types.

## Scope constraints

- This branch addresses only P1-3.
- Do not repair or rename the old 405 endpoint.
- Remove `/profile` because its only product purpose is public-ID friend management.
- Remove the play-page friend button, frontend friend client/store/types, friend E2E flow, API router, and friend-only schemas.
- Preserve `Friendship`, its relationships, database tests, and `UserManager` helpers; no destructive migration.
- Narrative uses of “friend/好友” are story-domain relationships and must remain.

### Task 1: Lock the retired-feature contract with RED tests

**Files:**
- Replace: `tests/test_api_friends.py`
- Modify: `tests/test_shift_left_e2e_contract_no_mock.py`
- Modify: `frontend/src/__tests__/pages/PlayPage.test.tsx`

- [ ] Add backend tests proving every former `/api/friends` route returns 404 and is absent from OpenAPI.
- [ ] Move former friend routes from active browser contracts to deprecated browser contracts.
- [ ] Replace the PlayPage navigation assertion with an assertion that no friend/social button is rendered.
- [ ] Run the three focused suites and confirm they fail for the old registered router and visible button.

### Task 2: Remove the backend runtime surface

**Files:**
- Delete: `src/api/routers/friends.py`
- Modify: `src/api/main.py`
- Modify: `src/api/schemas.py`
- Modify: `tests/test_gate_preflight_no_mock.py`
- Preserve: `src/database/models.py`, `src/database/user_manager.py`, friendship DB tests

- [ ] Remove the router import/registration and friend-only request/response schemas.
- [ ] Replace the preflight check that reads the deleted router with a contract that verifies the router is not imported or registered.
- [ ] Run retired-route and API contract tests GREEN.
- [ ] Confirm the database friendship model/helper tests remain unchanged.
- [ ] Commit the backend retirement.

### Task 3: Remove all frontend consumers and UI

**Files:**
- Delete: `frontend/src/app/profile/page.tsx`
- Delete: `frontend/src/__tests__/pages/ProfilePage.test.tsx`
- Delete/replace: `frontend/e2e/friends-system.spec.ts`
- Modify: `frontend/src/app/play/page.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/stores/useUserStore.ts`
- Modify: `frontend/src/__tests__/stores/useUserStore.test.ts`
- Modify: `frontend/src/__tests__/pages/WelcomePage.test.tsx`

- [ ] Remove the friend button and unused icon import from PlayPage.
- [ ] Remove `api.friends`, `FriendInfo`, `FriendRequestInfo`, friend state, cache, and actions.
- [ ] Simplify user-store tests and shared store mocks to auth-only state/actions.
- [ ] Replace the old friend-flow E2E with retirement coverage: `/profile` renders not-found and all former API paths return 404.
- [ ] Run focused Jest, TypeScript, and Playwright/source-contract tests GREEN.
- [ ] Commit the frontend retirement.

### Task 4: Regenerate contracts and verify no runtime references

**Files:**
- Modify: `frontend/src/types/openapi-schema.json`
- Modify: `frontend/src/types/api-generated.d.ts`

- [ ] Export the current OpenAPI schema and regenerate TypeScript declarations.
- [ ] Search runtime code for `/friends`, `api.friends`, friend store actions, `/profile`, and the visible “好友” button; only retirement tests/docs or narrative-domain uses may remain.
- [ ] Run `git diff --check`, focused backend/frontend tests, and strict TypeScript.
- [ ] Run `./test.sh all` and browser-smoke the retired UI/routes.
- [ ] Audit the diff against `origin/main`, update this checklist with exact evidence, and create one draft PR titled `refactor(friends): remove retired friend feature`.
