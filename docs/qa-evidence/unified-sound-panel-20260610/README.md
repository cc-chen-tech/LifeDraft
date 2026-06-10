# Unified Sound Panel QA Evidence

Date: 2026-06-10
Branch: `codex/redesign-unified-sound-main-20260610c`

## Scope

Verified the local sound UI on `http://localhost:3023/e2e-regression?globalVoice=1`.

## Browser Checks

Desktop viewport `1440x900` and mobile viewport `390x844` both exposed:

- one expanded group named `音乐和朗读`
- two peer channel groups: `背景音乐` and `故事朗读`
- no nested `region` inside `unified-sound-panel`
- no collapsed mini bar while expanded
- one shared music status and one shared narration status in the overview
- one `自动朗读` control inside the narration channel
- no `手动朗读` duplicate status in the overview
- no blocking `音乐服务暂不可用` message while playable music exists

Screenshots:

- `desktop.png`
- `mobile.png`

## Commands

```bash
npx jest --runTestsByPath src/__tests__/components/GlobalMusicPlayer.test.tsx src/__tests__/components/game/MusicPlayer.test.tsx --runInBand --testNamePattern="does not duplicate music|已有可播放音乐"
npx jest --runTestsByPath src/__tests__/components/GlobalMusicPlayer.test.tsx src/__tests__/components/StoryVoiceControls.test.tsx src/__tests__/components/game/MusicPlayer.test.tsx src/__tests__/pages/PlayPage.test.tsx --runInBand
npx openspec validate unify-sound-controls-ui --strict
npm run test:types
```

All commands passed locally.
