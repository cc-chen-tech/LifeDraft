# Unified Audio Panel QA Evidence

Date: 2026-06-10

## Scope

This evidence covers the frontend redesign that merges music and story narration into a single sound control surface.

## 2026-06-10 Follow-up

The expanded surface now renders as one two-channel sound mixer:

- The shared overview row remains the only top-level "声音" header.
- Background music is exposed as the peer channel group `背景音乐`.
- Story narration is exposed as the peer channel group `故事朗读`.
- Embedded `MusicPlayer` and `StoryVoiceControls` hide their own duplicate `音乐` / `朗读` headings inside this mixer.

## Browser Check

- URL: `http://localhost:3210/e2e-regression`
- Viewport: 1440 x 1000
- Screenshots:
  - `01-e2e-regression-initial.png`
  - `02-sound-panel-expanded.png`

The regression fixture confirms the collapsed global sound bar renders as one compact sound control plus expand/collapse. The fixture does not inject a production `activeReadingContext` into the global player, so the expanded browser screenshot only shows the music section. The production reading section is covered by unit tests in `GlobalMusicPlayer.test.tsx` and `PlayPage.test.tsx`.

## Verification

- `npx jest --runTestsByPath src/__tests__/components/GlobalMusicPlayer.test.tsx src/__tests__/components/StoryVoiceControls.test.tsx src/__tests__/pages/PlayPage.test.tsx --runInBand`
- `npx openspec validate unify-sound-controls-ui --strict`
- `TEST_NAMESPACE=unified-audio-panel-20260610 ./test.sh preflight`
