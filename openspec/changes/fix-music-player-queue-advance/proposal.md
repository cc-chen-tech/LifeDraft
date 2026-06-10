## Why

Generated MiniMax tracks are inserted into the persistent playlist queue after the
current NetEase baseline song. The player UI still advanced by the stale
`recommendation.songs` array captured when the audio element was created. If AI
music arrived while the current song was playing, the ended handler skipped the
generated queue head and played the old NetEase next song instead.

## What Changes

- Add a MusicPlayer regression test for current-song completion after an AI track
  is inserted into the future queue.
- Route ended playback, manual next, and stall-recovery switching through the
  playlist queue advance action first.
- Keep the old recommendation-array fallback only when no playlist queue advance
  is available.

## Impact

- `frontend/src/components/game/MusicPlayer.tsx`
- `frontend/src/__tests__/components/game/MusicPlayer.test.tsx`
