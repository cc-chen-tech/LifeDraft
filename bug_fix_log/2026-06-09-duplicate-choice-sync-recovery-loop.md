# Duplicate choice-sync recovery loop

Date: 2026-06-09

## Severity

P1 gameplay blocker. During production QA, a completed choice could leave the player stuck around "正在使用备用模式" / "恢复当前进度" instead of entering the result stage.

## Reproduction Evidence

- Production QA game reached week 1 round 1 after a story rewrite.
- After selecting "致电陈思颖确认明天", the UI stayed in long-running generation and recovery states.
- Screenshots:
  - `docs/qa-evidence/2026-06-09-pr70-production/49-long-generation-recovery.png`
  - `docs/qa-evidence/2026-06-09-pr70-production/50-after-restore-progress.png`
  - `docs/qa-evidence/2026-06-09-pr70-production/51-after-fallback-wait.png`
  - `docs/qa-evidence/2026-06-09-pr70-production/52-after-fallback-wait-2.png`
- ECS backend logs showed the first sync fallback completed and saved the choice result, then a duplicate `POST /api/games/101/choice-sync` saw `current_event=None` and returned `400` with `choice_already_processed`.

## Root Cause

The non-streaming `choice-sync` fallback was not idempotent. If a long-running fallback request completed server-side but the browser retried or restored progress before consuming the success response, the duplicate request found `current_event_data` already cleared and returned an error. The frontend recovery path could then remain in recovery/fallback UI even though the latest round result was already persisted in `round_history`.

## Fix

- Added an idempotent recovery path for `choice-sync` and `custom-choice-sync`.
- When `current_event` is missing because the choice was already processed, the sync endpoint now reconstructs a normal choice result from the latest saved `round_history` entry.
- SSE endpoints still require a current event; this fix is scoped to the fallback endpoints that are allowed to recover from interrupted client/network state.

## Regression Test

- Added `tests/test_choices_router.py::TestMakeChoiceEndpoint::test_choice_sync_returns_latest_result_when_choice_already_processed`.
- Verified RED first: the test failed with `422` under the previous behavior.
- Verified GREEN after the fix: the test returns the saved `story_continuation`, `summary`, effects, warnings, and result flags with `200`.

## Verification

- `python -m pytest tests/test_choices_router.py::TestMakeChoiceEndpoint::test_choice_sync_returns_latest_result_when_choice_already_processed -q`

## Follow-up

- Continue production QA from a fresh game after deployment and confirm that duplicate/retry choice processing enters the result stage instead of returning to the recovery loop.
