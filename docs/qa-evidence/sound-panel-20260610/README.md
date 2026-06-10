# Unified Sound Panel QA Evidence

Date: 2026-06-10
Branch: `codex/redesign-sound-panel-main-20260610b`

## Scope

Verified the local unified sound panel on `http://localhost:3021/e2e-regression?globalVoice=1`.

## Browser Checks

Desktop and mobile viewports both exposed exactly:

- one expanded `音乐和朗读` group
- one `背景音乐` group
- one `故事朗读` group
- one `朗读故事` button inside the panel
- one `选择朗读声音` selector inside the panel
- one `自动朗读` checkbox inside the panel
- one music status in the shared overview
- one narration status in the shared overview
- no `手动朗读` overview badge

Screenshots:

- `desktop-after.png`
- `mobile-after.png`

## Commands

```bash
npx jest --runTestsByPath src/__tests__/components/GlobalMusicPlayer.test.tsx src/__tests__/components/StoryVoiceControls.test.tsx src/__tests__/pages/PlayPage.test.tsx --runInBand
npx openspec validate unify-sound-controls-ui --strict
npm run test:types
./test.sh preflight
```

All commands passed.
