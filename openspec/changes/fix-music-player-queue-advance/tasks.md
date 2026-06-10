## 1. Tests

- [x] Add a MusicPlayer regression test where an AI-generated track is inserted while the current NetEase song is playing.
- [x] Verify the test fails because the ended handler plays the stale NetEase next song.

## 2. Fix

- [x] Advance the persisted playlist queue before choosing a fallback recommendation song.
- [x] Apply the same queue-first behavior to manual next and stall-recovery switching.

## 3. Verify

- [x] Run the focused MusicPlayer Jest test.
- [x] Run related music store queue tests.
- [x] Run frontend type checks.
- [x] Run OpenSpec validation.
