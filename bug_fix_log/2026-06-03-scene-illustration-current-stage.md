# 2026-06-03 Scene Illustration Current Stage Fix

## Problem

Scene illustrations could remain stuck on an old week-1 subway image while the current story had advanced to week 4 escape, residential building, and evidence scenes. Refresh/regenerate flows also had unclear feedback when the backend accepted generation but the image was not ready yet.

## Root Cause

- `useSceneImageStore.fetchRoundSceneImage` did not clear stale `eventSceneImage` or `resultSceneImage` before fetching a different `week/round/stage` key.
- The store normalized `scene.week` with `scene.week || week`, so a valid week `0` response could be relabeled as the current requested week, making an old week-1 image appear current.
- 202 Accepted responses from the scene image endpoint returned a JSON body without `scene_id`; the store treated that like an empty response and ended loading without a clear generation-in-progress state.
- The result-stage refresh button used `currentRound` instead of the just-completed round.
- The backend scene-image SSE contract was missing the latest-event cache and route, so frontend subscriptions had no usable event endpoint.
- During review, the new SSE route also exposed a permission bug: cached scene events were readable by unauthenticated users or by another user who guessed a `game_id`.

## Fix

- Clear mismatched current scene images when fetching a new scene key.
- Use nullish fallback for `week` and reject mismatched `week/round/stage` responses instead of relabeling them.
- Keep `isLoadingRoundSceneImage` true for 202 generation-in-progress responses.
- Show an explicit in-progress message while refreshing/generating an existing scene and keep refresh/regenerate actions disabled.
- Use `Math.max(0, currentRound - 1)` for result-stage scene refresh/regenerate.
- Add scene-image SSE latest-event cache, publish helper, route, and background success/failure publishing.
- Require authentication and game ownership on the scene-image SSE endpoint; unauthenticated users now get 401 and users who do not own the game get 404.

## Verification

- `cd frontend && npx jest --runInBand src/__tests__/stores/useSceneImageStore.test.ts src/__tests__/components/RoundSceneImage.test.tsx src/__tests__/pages/PlayPage.test.tsx`
  - Result: 3 suites passed, 84 tests passed.
- `python3 -m pytest tests/test_scene_image_constraint_contract.py tests/test_scene_image_integrity_narrow_contract.py tests/test_scene_image_sse_contract.py tests/test_scene_image_sse_integration.py tests/test_gate_real_db_no_mock.py -k scene_image`
  - Result: 15 passed, 2 deselected.
- `python3 -m pytest tests/test_scene_image_sse_contract.py tests/test_scene_image_sse_integration.py -q`
  - Result: 10 passed.
