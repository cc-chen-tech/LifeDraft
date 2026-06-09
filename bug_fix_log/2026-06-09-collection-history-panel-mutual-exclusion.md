# 2026-06-09 Collection and History Panel Mutual Exclusion

## Severity

P1 UX correctness. The issue can leave the play page in a mixed history-reading and collection-panel state, making navigation and follow-up actions confusing.

## Root Cause

`/play` used independent state for the collection sheet and the history drawer/history-reading mode. The collection button only opened `showCollection`; it did not close the history drawer or exit history-reading mode. The history button opened the history drawer without first closing the collection sheet.

Both panels are side-panel tools, so users should be able to switch directly from one top-bar entry to the other. The original modal Sheet behavior prevented that direct switch by isolating the page behind the open sheet.

## Reproduction

1. Enter `/play` with an active game.
2. Open history and select/read a historical round, or otherwise enter a history-related state.
3. Open collection from the play header.
4. Observe that collection can appear while the page still behaves as history-reading context.

## Fix

- Added `handleOpenCollection` in `frontend/src/app/play/page.tsx`.
- Opening collection now closes the history drawer and calls `handleBackToCurrent()` when currently viewing history.
- Added `handleOpenHistoryPanel` so opening history closes collection first.
- Updated button handlers to route through these mutual-exclusion functions.
- Changed the history and collection sheets to non-modal side panels with transparent, non-intercepting overlays, so top-bar switching remains available while a side panel is open.

## Regression Tests

- `frontend/src/__tests__/pages/PlayPage.test.tsx`
  - `closes history mode before opening collection panel`
  - `opens history panel when history button clicked`
- `frontend/e2e/collection-panel-cache.spec.ts`
  - `历史回顾与收集面板不能同时打开`

## Verification

- Red test: temporarily reverted the production `PlayPage` handler changes and confirmed the new unit test failed.
- Green focused unit test:
  - `npx jest src/__tests__/pages/PlayPage.test.tsx --runInBand --testNamePattern='closes history mode before opening collection panel|opens history panel when history button clicked'`
  - Result: 2 passed.
- Frontend layer:
  - `./test.sh frontend`
  - Result: TypeScript passed; Jest 99 suites passed; integration 1 suite passed.
- Browser E2E layer:
  - `TEST_RUN_ROOT=/tmp/story2-codex-test-runs TEST_NAMESPACE=history_collection_1780968988 ./test.sh e2e`
  - Result: core 302 passed; music queue 1 passed; character settings 1 passed; story voice 8 passed; MiniMax audio 4 passed; collection/entity 27 passed.

## Notes

One earlier E2E run under repo-local `.test-runs` failed with SQLite `attempt to write a readonly database`, then cascaded into auth and collection failures. The same run also reported a missing Playwright log directory. Re-running with `TEST_RUN_ROOT=/tmp/story2-codex-test-runs` completed successfully, so that failure is recorded as a local runtime-directory issue rather than a product regression.
