## Why

Music QA uncovered that `NeteaseMusicClient` had regressed to the old `localhost:3000` default and no longer exposed the shared song URL cache or availability check expected by the music service contracts. That can make Docker/ECS deployments call the frontend port instead of the music API, repeatedly fetch short-lived CDN URLs, and fail slowly when the upstream service is degraded.

## What Changes

- Restore the Docker/ECS-safe default music API URL: `http://music-api:3001`.
- Restore class-level song URL caching with an 8-minute TTL.
- Add cached music service availability checks with a 3-second timeout.
- Retry transient search and song URL 5xx/network failures while preserving fast failure for 4xx responses.

## Impact

- Backend music client: `src/services/music_service.py`.
- Contract coverage: music URL, cache, health, retry, recommendation, playlist, MiniMax queue, and frontend player tests.
