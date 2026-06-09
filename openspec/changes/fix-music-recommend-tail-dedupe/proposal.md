## Why

The UX report still shows tail music failures after the first negative-cue fix: repeated title families such as "绅士" and "红尘客栈" can fill the recommendation list, and weak vocal-pop matches can still reach the persistent playlist. This makes background music feel mismatched and can cause the player queue to advance into the wrong repeated song.

## What Changes

- Extend post-search rejection for reported modern vocal-pop and meme/title-family mismatches.
- Normalize reported title families so cover/remix/acoustic/live/version variants dedupe as one recommendation.
- Apply the same title-family dedupe when merging recommendations into the persistent music playlist, not only inside the NetEase search pool.
- Preserve explicit playable instrumental/score candidates and existing current playback.

## Capabilities

### New Capabilities

- `story-music-recommendation`: story-conditioned music recommendations, post-search filtering, and playlist queue quality for recommended tracks.

### Modified Capabilities

None.

## Impact

- Backend music recommendation ranking and pool selection in `src/services/music_service.py`.
- Persistent music playlist merge policy in `src/services/music_playlist_service.py`.
- Contract and DB tests for recommendation filtering and queue save-read behavior.
- `test.sh` already includes the affected test layers; no new skipped or mocked tests are introduced.
