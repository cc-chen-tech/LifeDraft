# Unified Sound Controls QA

Date: 2026-06-10
Branch: `codex/unified-sound-controls-20260610`

## Scope

Verified the redesigned global sound UI for story music and story narration.

## Browser Evidence

- URL: `http://localhost:19123/e2e-regression?globalVoice=1`
- The collapsed sound bar exposed separate music and narration actions.
- Clicking `朗读故事` from the collapsed bar started the narration request without expanding the panel.
- Backend audio ready state changed the collapsed narration action to `播放朗读语音`.
- The expanded unified sound panel contained both `场景音乐` and `故事朗读`.
- The ready narration state did not show the redundant `停止` action.

Screenshot: `docs/qa-evidence/unified-sound-controls-20260610-ready.png`

## Verification

- `npx jest src/__tests__/components/GlobalMusicPlayer.test.tsx --runInBand --testNamePattern='sibling controls|starts narration'`
- `npx jest src/__tests__/components/StoryVoiceControls.test.tsx --runInBand --testNamePattern='only ready'`
- `npx jest src/__tests__/components/GlobalMusicPlayer.test.tsx src/__tests__/components/GlobalMusicPlayer.escape.test.tsx src/__tests__/components/StoryVoiceControls.test.tsx --runInBand`
- `openspec validate unify-sound-controls-ui --strict`
- `TEST_NAMESPACE=unified-sound-controls-20260610 ./test.sh preflight`
