# Story101 production QA report - 2026-06-09

## Scope

Production target: https://story101.live

Validated commit before QA: `eb06f363e180d3af9ef0e239292ca683c35a0154`

Evidence directory: `docs/qa-evidence/2026-06-09-pr70-production/`

The QA flow started from a fresh registered user, created a new modern realistic game, entered play, exercised creation regeneration/save/details, story choices, rewrite, life summary, collection, history, settings, TTS voices, auto-read, MiniMax music, NetEase/base queue, player switching, and scene illustration loading. The run did not honestly reach week 4 because a production gameplay blocker occurred during week 1 after a rewrite and choice. This report preserves that blocker instead of claiming a false pass.

## Environment State

- Local latest `main` was fully tested with `./test.sh all`.
- GitHub Actions for remote `main` still failed before runner startup with empty job steps and `log not found`, so they were treated as platform/runner failures rather than code failures.
- ECS was manually deployed and verified healthy before this QA pass.

## High Severity Findings

### P1 - Duplicate choice-sync recovery loop after long fallback

Status: fixed locally, full local test suite passed, production redeploy pending after commit.

Evidence:

- `49-long-generation-recovery.png`
- `50-after-restore-progress.png`
- `51-after-fallback-wait.png`
- `52-after-fallback-wait-2.png`

Reproduction:

1. Create a fresh realistic modern game.
2. Reach week 1 round 1.
3. Rewrite the story.
4. Pick the option "致电陈思颖确认明天".
5. Wait through long generation/fallback.
6. Click recovery when offered.

Observed:

- Backend had already saved the choice result.
- A duplicate `choice-sync` request returned `choice_already_processed`.
- The browser stayed around fallback/recovery UI instead of cleanly entering result state.

Root cause:

`choice-sync` was not idempotent. When a fallback request completed server-side but the browser retried/restored before consuming the success response, the duplicate request found `current_event_data` cleared and returned an error rather than the persisted latest round result.

Fix:

`choice-sync` and `custom-choice-sync` now reconstruct a normal choice result from the latest saved `round_history` when the choice was already processed.

Regression:

- `tests/test_choices_router.py::TestMakeChoiceEndpoint::test_choice_sync_returns_latest_result_when_choice_already_processed`

Verification:

- `python -m pytest tests/test_choices_router.py tests/test_error_recovery_contract.py -q`
- `npx jest src/__tests__/hooks/choiceUtils.test.ts --runInBand`
- `./test.sh contract`
- `./test.sh all`

## Medium Findings

### P2 - Generated wealth setting differs from in-game HUD

Status: unfixed.

Evidence:

- Character creation generated an initial wealth detail of `¥50,000`.
- The in-game HUD showed `财富: ¥10,000`.

Risk:

This weakens trust in generated character settings. A backend API contract test already covers one create-game path, so the remaining defect is likely in the production creation/frontend state path or a display fallback.

### P2 - Rewrite latency and feedback

Status: unfixed.

Evidence:

- Rewrite took over one minute in production.
- The modal stayed in `正在改写中...` without enough progress detail.

Risk:

The rewrite eventually succeeded and improved text, but the wait state can look stuck.

### P2 - Creation regeneration controls lose discoverability after feedback

Status: unfixed.

Evidence:

- After using "根据意见修改", the overall feedback input and full regeneration affordance became less visible.

Risk:

Users may believe only section-level feedback remains available.

### P2 - TTS state labels are inconsistent

Status: unfixed.

Evidence:

- Voice switching worked for warm female, calm male, and clear neutral.
- Some states showed `播放语音` plus `停止`, or `正在生成语音` while another audio was already playable.

Risk:

The audio system works, but labels make it difficult to know whether the user is generating, playing, paused, or can resume.

### P2 - Music availability message conflicts with playback

Status: unfixed.

Evidence:

- MiniMax generated tracks were queued/playing.
- At times the UI still showed `音乐服务暂不可用`.

Risk:

The player state and service status text can contradict each other.

### P2 - Life summary week range reads awkwardly

Status: unfixed.

Evidence:

- Week 1 summary title displayed `第1-1周`.

Risk:

Minor polish issue; should be `第1周` for a single-week summary.

## Narrative Quality Notes

Strengths:

- Opening and week 1 story generally followed the requested realistic modern Shanghai/product-manager setup.
- Paragraphing and Chinese punctuation were mostly readable.
- Character continuity for 张明远、李诗涵、陈思颖 was better than previous runs.

Issues:

- Before rewrite, one week 1 midweek story repeated "周一" timing in a confusing way and leaned too much into ambiguous emotional tension.
- Rewrite feedback improved timeline clarity, but the generation path then hit the P1 recovery-loop blocker above.

## Follow-up Order

1. Deploy and production-retest the fixed duplicate `choice-sync` path.
2. Continue the same deep QA flow from a fresh game to at least week 4.
3. Fix generated wealth mismatch.
4. Fix rewrite progress feedback.
5. Fix TTS/music state copy consistency.
6. Fix single-week summary title formatting.
