# Choice Recovery Used Stale Round History - 2026-06-09

## Issue

Production QA on `story101.live` game `105` reached Week 3 weekend. After selecting
`主动与父亲聊查账事宜`, the page stayed in a low-feedback generation state for about
60 seconds and then exposed `恢复当前进度`. Clicking recovery appended a result under
the selected choice, but the result text came from the previous Lin Xiaowei contract
negotiation round and the primary button still showed `进入周末`.

Evidence:
- `docs/qa-evidence/2026-06-09-heartbeat-0951-production/week3-weekend-post-choice-recover-needed.png`
- `docs/qa-evidence/2026-06-09-heartbeat-0951-production/week3-recover-regressed-to-enter-weekend.png`
- Browser state API showed `round_info.current_round=2` and `current_event.options`
  still contained the original weekend options, while `round_history` latest entry
  had `choice="要求林晓薇修改第七款"`.

## Root Cause

`recoverStoryFromRoundHistory()` always appended the latest `round_history` entry
when recovering from interrupted choice streams. Production `round_history` entries
include a `choice` field, but the recovery code ignored it. When the current choice
had not actually been persisted, the latest history entry could belong to a previous
round, causing stale story text to be displayed as if it were the current result.

## Regression Test

Added a unit test in:

- `frontend/src/__tests__/hooks/choiceUtils.test.ts`

The test reproduces a current choice of `主动与父亲聊查账事宜` while the saved history
entry has `choice="要求林晓薇修改第七款"`. Before the fix, the test failed because the
stale continuation was appended. After the fix, recovery returns `false` and leaves
the story text untouched.

## Fix

Updated `frontend/src/hooks/game/choiceUtils.ts` so history recovery:

- normalizes choice text before comparing;
- prefers the newest history entry whose `choice` matches the current choice;
- skips recovery when history entries have choice metadata but none match;
- keeps legacy compatibility for older history/test data that lacks `choice`.

This prevents the frontend from presenting a stale previous-round continuation as
the result of a new user choice. It does not solve the underlying server-side
interrupted choice persistence gap; it prevents false recovery and data corruption
in the UI.

## Verification

- `cd frontend && npx jest src/__tests__/hooks/choiceUtils.test.ts --runInBand --runTestsByPath`
  - Result: 38 passed

## Residual Risk

The production flow still needs a backend/state-machine fix for interrupted weekend
choice persistence. If the backend does not save the selected choice and advance
`round_info`, the frontend should show a recoverable error or retry path instead of
incorrectly advancing. That follow-up should cover the choice SSE/fallback contract
from request through `round_history`, `current_event`, and `round_info` updates.
