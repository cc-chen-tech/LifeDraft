# Sound UI Merge Evidence - 2026-06-10

## Scope

This evidence covers the frontend layout change that merges background music and story narration into one expanded sound mixer.

## Local Browser Smoke

- URL: `http://localhost:3219/e2e-regression?globalVoice=1`
- Dev server: `cd frontend && PORT=3219 npm run dev -- --webpack`
- Screenshot: `docs/qa-evidence/sound-ui-merged-20260610.png`

Observed:

- The collapsed entry remains one global `声音` control.
- The expanded panel shows one `声音` overview row.
- The same panel contains sibling `音乐` and `朗读` channel sections.
- Voice selection and auto-read controls are shown inside the `朗读` channel.

Note: the smoke test intercepts voice APIs and uses a tiny fake audio body, so the screenshot is not proof of real MiniMax audio playback. Real backend audio remains covered by the voice-reading contract tests and production smoke checks.

## Automated Verification

- `cd frontend && npx jest src/__tests__/components/GlobalMusicPlayer.test.tsx --runInBand --testNamePattern='semantic channel headings'`
- `cd frontend && npx jest src/__tests__/components/GlobalMusicPlayer.test.tsx src/__tests__/components/StoryVoiceControls.test.tsx src/__tests__/pages/PlayPage.test.tsx --runInBand`
- `npx openspec validate unify-sound-controls-ui --strict`
