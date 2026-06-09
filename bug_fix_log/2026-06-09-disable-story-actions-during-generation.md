# Disable Story Actions During Generation - 2026-06-09

## Problem

Production QA on `https://story101.live` found that users can trigger story actions while the current story is still streaming or being checked.

Observed evidence:

- On `/story/opening`, the opening text could appear truncated while the illustration was still generating, but the primary continue action was already visible.
- Self-review found an additional race: immediately after a newly generated opening story completed, there was a short delay before illustration generation flipped the image store loading state. During that delay, `开始我的人生` could still become clickable.
- On `/play`, `朗读故事`, `重新生成`, `改写`, and `人生总结` were enabled while the page still showed generation states such as `正在处理中...`, `正在检查故事一致性...`, and `正在生成选项...`.
- After waiting, the same story usually completed with paragraphs, punctuation, options, and scene media. This indicates a transient incomplete-content state rather than a final story-generation failure.

Severity: P1. The issue can cause users to read, rewrite, regenerate, or summarize partial story text, making the product feel like it returned broken or truncated prose.

## Root Cause

The play page computed completion for media work with `phase === "options" || phase === "result"`, but it did not pass an explicit "current story is still busy" contract into action components.

Component gaps:

- `ChatBar` disabled rewrite only when there was no story text or history mode was active. It did not know about `loading`, `generating`, or `choosing` phases.
- `ChatBar` allowed regeneration and life summary while the current story was not stable.
- `StoryVoiceControls` disabled the primary read button only while voice generation was already loading. It did not prevent starting TTS from partial story text.

## Regression Tests

Added targeted component tests:

- `frontend/src/__tests__/components/ChatBar.test.tsx`
  - Verifies `重新生成`, `改写`, and `人生总结` are disabled while `isStoryBusy` is true.
  - Verifies disabled regenerate and summary actions do not call handlers or the summary API.
- `frontend/src/__tests__/components/StoryVoiceControls.test.tsx`
  - Verifies the primary read button is disabled and labeled `故事生成完成后可朗读` while `isStoryReady` is false.
- `frontend/src/__tests__/pages/OpeningStoryPage.test.tsx`
  - Verifies `开始我的人生` is disabled while the opening illustration is still generating.
  - Verifies a newly generated opening story keeps the start button disabled while the opening illustration is queued but not yet in store loading state.

## Fix

Code changes:

- `frontend/src/app/play/page.tsx`
  - Added `isCurrentStoryBusy` for `loading`, `generating`, and `choosing`.
  - Passes `isStoryBusy` to `ChatBar`.
  - Passes `isStoryReady={storyReadyForCompletedMedia}` to current-story `StoryVoiceControls`.
- `frontend/src/components/game/ChatBar.tsx`
  - Added `isStoryBusy` prop.
  - Disables regenerate, rewrite, rewrite submit, and life summary while the story is busy.
  - Keeps explicit guards in async handlers so disabled state cannot be bypassed by script or keyboard paths.
- `frontend/src/components/game/StoryVoiceControls.tsx`
  - Added `isStoryReady` prop.
  - Disables primary reading and returns early from the handler until story generation is complete.
  - Shows user-facing disabled label `故事生成完成后可朗读`.
- `frontend/src/app/story/opening/page.tsx`
  - Added an `openingReadyToStart` gate.
  - Disables the start-game button while the opening illustration is still generating.
  - Tracks newly queued opening illustration generation explicitly to close the delay before image loading state is visible.
  - Keeps a handler-level guard so navigation cannot be triggered while the opening content is unstable.

## Verification

Commands run:

```bash
cd frontend && npx jest src/__tests__/components/ChatBar.test.tsx src/__tests__/components/StoryVoiceControls.test.tsx --runInBand
cd frontend && npx jest src/__tests__/pages/OpeningStoryPage.test.tsx src/__tests__/components/ChatBar.test.tsx src/__tests__/components/StoryVoiceControls.test.tsx --runInBand
npm --prefix frontend run test:types
```

Results:

- `3` Jest suites passed.
- `52` tests passed, with `1` pre-existing skipped test.
- TypeScript strict check passed.

## Follow-up

Remaining related UX work:

- Investigate the `查看设定详情` clickability issue observed in production browser QA, where DOM click works but normal browser-agent click can hang.
- Consider shortening the first round or adding stronger progress copy while consistency checks and option generation run longer than one minute.
