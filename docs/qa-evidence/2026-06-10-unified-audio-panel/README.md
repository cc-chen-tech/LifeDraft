# Unified Audio Panel QA Evidence

Date: 2026-06-10

## Scope

This evidence covers the frontend redesign that merges music and story narration into a single sound control surface.

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
