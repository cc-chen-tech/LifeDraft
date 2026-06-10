## 1. Reproduce

- [x] 1.1 Run music client URL/cache/health tests and confirm default URL/cache/health contracts fail on current main.
- [x] 1.2 Run the broader music recommendation/player suite and confirm failures are isolated to `NeteaseMusicClient`.

## 2. Implementation

- [x] 2.1 Set the default Netease API base URL to `http://music-api:3001`.
- [x] 2.2 Restore class-level song URL cache and 480-second TTL.
- [x] 2.3 Restore cached availability checks with a 3-second timeout.
- [x] 2.4 Restore retry handling for transient search and song URL failures.

## 3. Verification

- [x] 3.1 Run focused URL/cache/health/retry tests.
- [x] 3.2 Run broader music recommendation, MiniMax generation, playlist, cache, and scene-matching contract tests.
- [x] 3.3 Run focused frontend music player/store tests.
- [x] 3.4 Run the browser regression proving generated AI music enters the future queue without replacing the current track.
