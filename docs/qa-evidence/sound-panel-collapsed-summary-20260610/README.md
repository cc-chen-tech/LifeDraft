# Sound Panel Collapsed Summary QA - 2026-06-10

Scope: verify that the global sound UI presents music and narration as one combined control surface before and after expansion.

## Local Browser Verification

- Worktree: `/Users/luicy/story2/.worktrees/unify-audio-ui-20260610`
- URL: `http://localhost:3124/e2e-regression?globalVoice=1`
- Desktop viewport: `1280x900`
- Mobile viewport: `390x844`

## Verified Behavior

- The collapsed global sound bar exposes one entry point named `展开声音`.
- The collapsed bar shows peer channel summaries for `背景音乐` and `故事朗读`.
- The collapsed bar does not expose narration playback buttons.
- The expanded panel exposes one `音乐和朗读` group.
- The expanded panel contains sibling `背景音乐` and `故事朗读` channel groups.

## Evidence

- `desktop-collapsed.png`
- `desktop-expanded.png`
- `mobile-collapsed.png`
- `mobile-expanded.png`
- `latest-desktop-collapsed.png`
- `latest-desktop-expanded.png`

## Commands

```bash
NODE_PATH=/Users/luicy/story2/frontend/node_modules PATH=/Users/luicy/story2/frontend/node_modules/.bin:$PATH jest --runTestsByPath src/__tests__/components/GlobalMusicPlayer.test.tsx src/__tests__/components/StoryVoiceControls.test.tsx src/__tests__/pages/PlayPage.test.tsx --runInBand
npx openspec validate unify-sound-controls-ui --strict
npm run test:types
git diff --check
```
