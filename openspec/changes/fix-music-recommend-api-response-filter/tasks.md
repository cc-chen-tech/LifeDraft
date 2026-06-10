## 1. Root Cause

- [x] Confirm service-level filters exist for reported title families but the router still returned dirty songs if the service output contained them.
- [x] Reproduce the API boundary leak with a router test using playable `绅士`, `红尘客栈`, and Anime OP recommendations.

## 2. Fix

- [x] Apply final music brief filtering inside `/api/music/recommend`.
- [x] Run that filtering before playback URL lookup so discarded songs do not slow the endpoint.

## 3. Verify

- [x] Run the new focused router regression.
- [x] Run the broader music router/recommendation suite.
- [x] Run `openspec validate fix-music-recommend-api-response-filter --strict`.
- [x] Run project preflight before commit.
