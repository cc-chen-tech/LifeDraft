## Why

Live browser testing on story101.live found that a newly created game can enter unrecoverable generation states: opening generation times out, retry can time out again, `/play` may show only `故事生成中...`, and collection recognition can remain stuck at `正在分析故事历史...`. These failures block normal play before week 4 and make recovery, login, and collection behavior unreliable.

## What Changes

- Make gameplay generation recovery deterministic: timeout, retry, refresh, and `/play` restore must always surface either playable content or an actionable recovery state.
- Align private-id login contracts so the saved one-time credential can be submitted and errors are specific enough to diagnose.
- Preserve canonical character settings from creation into opening and round generation, including era, role, gender, narrative person, and core premise.
- Gate collection recognition by system relationship/importance metadata instead of raw text mentions, and prevent stuck recognition/add states.
- Improve media degradation where music/image services fail or return unsuitable resources, especially mixed-content audio URLs.

## Capabilities

### New Capabilities
- `gameplay-generation-recovery`: Covers opening/round generation timeout handling, retry semantics, refresh recovery, and playable fallback states.
- `private-id-auth-contract`: Covers front-end/back-end payload alignment and recoverable login feedback for private IDs.
- `character-setting-continuity`: Covers preserving created character/world settings through opening story and subsequent rounds.
- `collection-recognition-gating`: Covers entity recognition based on relationship/importance metadata, de-duplication, empty results, and timeout states.
- `music-and-media-degradation`: Covers music/image failure handling and mixed-content-safe media URLs during gameplay.

### Modified Capabilities

None.

## Impact

- Backend routers: `src/api/routers/auth.py`, `src/api/routers/story.py`, `src/api/routers/games.py`, `src/api/routers/collection.py`, and possibly image/music routers.
- Game/AI services: generation/retry recovery, story prompt construction, collection/entity recognition services, and media recommendation/degradation services.
- Frontend play/create/auth/collection UI: recovery affordances, login payloads, loading/timeout messaging, and disabled button states.
- Tests: targeted pytest contract/DB tests, frontend unit/contract tests where available, and minimal Playwright regression for browser-only recovery behavior.
