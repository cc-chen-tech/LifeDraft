# PR #82 duplicate story voice controls

Date: 2026-06-10

## Problem

Integrating PR #82 (`codex/redesign-sound-panel-20260610`) into `main` introduced a real local E2E regression in the story voice and MiniMax audio suites.

## Reproduction evidence

Full local integration test on the PR #82 merge candidate failed in `./test.sh all` at Layer 5 E2E:

- `frontend/e2e/minimax-story-audio-generation.spec.ts`
  - `provider story narration attaches decodable audio without using browser speech fallback`
  - `auto-read stays off by default and starts only after final story when enabled`
- `frontend/e2e/story-voice-reading.spec.ts`
  - `reads current and historical story text through the backend asset API`

The direct red/green regression assertion reproduced the root problem:

```text
Expected: 1
Received: 2
Locator: getByTestId('voice-reading-audio-player')
```

The strict-mode error showed one audio element inside `故事朗读回归夹具` and one inside `sound-reading-section`.

## Root cause

`frontend/src/app/e2e-regression/page.tsx` started setting an active global reading target by default. The root layout already mounts `GlobalMusicPlayer`, and PR #82 embeds `StoryVoiceControls` inside that global sound panel when an active reading target exists.

The E2E regression page also mounts its own `StoryVoiceControls` with `showTestControls` for deterministic voice tests. As a result, the page had two independent audio elements and two control instances sharing the same story voice store state. The global embedded controls could also auto-read the initial fixture story immediately after the user enabled auto-read, before the final retry story was ready.

## Fix

- The default `/e2e-regression` route no longer mounts a global reading target.
- A global voice fixture remains available behind `?globalVoice=1` for targeted sound-panel checks.
- Story voice and MiniMax E2E helpers now assert that the regression page exposes exactly one `voice-reading-audio-player`, catching future duplicate-control regressions earlier.

## Verification

After the fix:

- `./test.sh e2e`: passed
  - main Playwright E2E: 303 passed
  - story voice supplement: 8 passed
  - MiniMax audio supplement: 4 passed
  - collection/entity supplement: 27 passed
- `./test.sh all`: passed
  - Preflight: PASS
  - Layer 1 mypy: PASS
  - Layer 2 imports: PASS
  - Layer 3 contract: PASS
  - Layer 4 db: PASS
  - Layer 5 e2e: PASS

## Status

Fixed locally and ready to push with the verified PR #82 merge.
