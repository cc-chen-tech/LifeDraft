# Deep UX P0 Fixes

Date: 2026-06-07
Branch: `codex/deep-ux-p0-fixes`
Base: `origin/main` at `d93d5833`

## Fixed in this branch

### 1. `PATCH /api/games/{id}/character-settings` returned 404

Reproduction:
- `tests/test_character_settings_api_contract.py` initially failed because the endpoint did not exist and returned framework-level 404.

Fix:
- Reintroduced an authenticated `PATCH /api/games/{game_id}/character-settings` endpoint.
- The endpoint loads the owned game, deep-merges late generated `character_settings`, persists via `save_game_progress`, and updates the live in-memory game session when present.
- Existing outdated tests that asserted the endpoint was removed were updated to the new contract.
- Synced generated OpenAPI artifacts so `/api/games/{game_id}/character-settings` appears in `frontend/src/types/openapi-schema.json` and `frontend/src/types/api-generated.d.ts`.

Verification:
- `pytest tests/test_character_settings_api_contract.py tests/test_character_settings_persistence_db.py tests/test_style_auto_match_integration.py -q`
- `python scripts/export_openapi.py`
- `cd frontend && npx openapi-typescript src/types/openapi-schema.json -o src/types/api-generated.d.ts`

### 2. Placeholder player names were treated as real surnames

Reproduction:
- Added a failing test where `"测试小可"` caused generated family members `"测试卫国"` and `"测试秀兰"` to survive unchanged.

Fix:
- Added family-setting post-processing that strips placeholder prefixes such as `测试`, `示例`, `玩家`, `主角`, `用户` from generated family member names.
- Added a prompt rule telling the model not to treat placeholder prefixes as surnames.
- Preserves real surnames such as `"张三" -> "张卫国"`.

Verification:
- `pytest tests/test_character_creation_deep.py tests/test_character_creation.py tests/test_name_integrity_contract.py -q`

### 3. Opening story SSE could complete with zero story text

Reproduction:
- Added a Jest test where `event: complete` with `{}` and no prior story chunk resolved successfully.

Fix:
- `streamOpeningStory` now accumulates streamed story chunks.
- If the stream completes without any streamed text and without `full_story`, it rejects with `Opening story stream completed without story text` and calls `onError`.
- Existing valid path of story chunks plus empty complete payload remains supported.

Verification:
- `npx jest src/__tests__/lib/sse.test.ts --runInBand`

### 4. SSE 5xx/retry and abrupt disconnect handling were missing

Reproduction:
- `pytest tests/test_sse_retry_contract.py tests/test_error_recovery_contract.py ...` failed on missing retry logic and missing `Stream ended without complete event`.

Fix:
- Added `fetchSSEWithRetry` with up to 3 attempts and exponential backoff for 5xx/502/504 or transient network failures.
- Applied it to `streamChoice`, `streamCustomChoice`, and `streamOpeningStory`.
- Aborted requests do not retry.
- Raw stream endings without complete/error/DONE now emit `Stream ended without complete event`.

Verification:
- `pytest tests/test_sse_retry_contract.py tests/test_sse_timeout_contract.py tests/test_generate_round_event_retry.py tests/test_error_recovery_contract.py tests/test_event_generation_race_db.py -q`
- `npx jest src/__tests__/lib/sse.test.ts --runInBand`

### 5. Opening story prompt did not list key people

Reproduction:
- Added a failing contract test showing `relationships.key_people` names and roles were absent from the opening story prompt.

Fix:
- Opening story prompt now lists key people and adds a hard constraint to prioritize listed family members and key people before inventing new characters.

Verification:
- `pytest tests/test_live_gameplay_recovery_collection_contract.py::test_opening_prompt_lists_key_people_as_story_constraints -q`

## Verified Already Fixed on Current `origin/main`

### MiniMax music bitrate

The reported `192000` bitrate issue was not present in the current base branch:
- `src/services/minimax_music_generation.py` uses `256000`.
- `tests/test_minimax_audio_generation_contract.py::test_minimax_music_generation_request_uses_url_output_and_audio_settings` passes.

## Browser Verification

The original report also mentioned that rewrite/rephrase/summary controls looked missing on the web UI. This branch did not need a UI code change for that symptom, but the existing regression coverage was rerun against this worktree:

- Built the frontend with `npm run build`.
- Started the production frontend with `npm run start -- --port 3000`.
- Started the FastAPI backend with `API_RELOAD=false python run_api.py`.
- Ran `npx playwright test e2e/rewrite-button-discoverable.spec.ts --config=.playwright-no-webserver.config.ts --project=core --project="Mobile Safari"` against the production frontend and backend with a temporary no-webServer config, then removed that temporary config.
- Result: 12/12 passed across desktop core and Mobile Safari projects, covering narrow mobile, mobile portrait, tablet portrait, desktop, and wide desktop viewport shapes.

Note: the repository's default local Playwright webServer path hit a local `EMFILE: too many open files` watcher limit when using `next dev`. Production build/start verification avoided that environment limit.

## Still Not Fully Addressed in This Branch

- Full live browser journey to week 4 was not rerun yet in this branch.
- Music recommendation semantic mismatch is still a separate P1 quality issue.
- Button function mismatch for summary/settings needs a separate focused reproduction if it still appears on the current UI.
- Entity collection returned zero in the report, but current unit contracts for entity fallback/current-event recognition are green; a full browser reproduction is still needed to prove the exact UI path.
