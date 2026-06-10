# Compact Sound UI Evidence - 2026-06-10

Scope: verify the global sound UI merges background music and story reading into one compact sound panel.

## Browser Fixture

- Worktree: `/Users/luicy/story2/.worktrees/merge-sound-reading-ui-20260610`
- URL: `http://127.0.0.1:3128/e2e-regression?globalVoice=1`
- Viewport: `1440x1000`
- Collapsed screenshot: `docs/qa-evidence/sound-ui-compact-global-collapsed-20260610.png`
- Expanded screenshot: `docs/qa-evidence/sound-ui-compact-global-expanded-20260610.png`

## Verified Behavior

- Collapsed visible mini bar exposes one action: `展开声音`.
- Collapsed visible mini bar does not expose music `播放` / `暂停` or story `朗读故事` actions.
- Expanded panel exposes one sound group: `音乐和朗读`.
- Expanded panel uses `sound-channel-list`, not the older `sound-mixer-grid`.
- Expanded panel contains compact peer channels `背景音乐` and `故事朗读`.
- Embedded music controls do not show recommendation lists or mood/environment chips.
- Embedded reading controls keep `朗读故事`, `选择朗读声音`, and `自动朗读` inside the same sound panel.

## Commands

```bash
cd /Users/luicy/story2/.worktrees/merge-sound-reading-ui-20260610/frontend
npx jest --runTestsByPath src/__tests__/components/GlobalMusicPlayer.test.tsx src/__tests__/components/StoryVoiceControls.test.tsx src/__tests__/pages/PlayPage.test.tsx --runInBand
npm run test:types
cd ..
npx openspec validate unify-sound-controls-ui --strict
```
