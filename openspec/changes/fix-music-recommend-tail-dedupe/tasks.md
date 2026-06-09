## 1. Tests

- [x] Add no-mock music recommendation contract coverage for the reported tail mismatches.
- [x] Add real DB playlist save-read coverage proving same title-family variants do not persist into the queue.
- [x] Verify the new tests fail before production code changes.
- [x] Add contract coverage proving NetEase search placeholders named like generated MiniMax tracks are filtered without rejecting real `ai_generated` tracks.

## 2. Fix

- [x] Extend negative-cue title-family matching for the reported songs.
- [x] Reuse title-family keys for final recommendation and persistent playlist dedupe.
- [x] Preserve current playback while filtering duplicate future queue items.
- [x] Filter generated-track placeholder names from search-backed recommendations while preserving real generated-track sources.

## 3. Verify

- [x] Run `openspec validate fix-music-recommend-tail-dedupe --strict`.
- [x] Run targeted music recommendation and playlist tests.
- [x] Run `./test.sh preflight`.
- [x] Run `./test.sh all`.
