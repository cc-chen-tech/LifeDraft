## Why

The UX report showed `/api/music/recommend` becoming unavailable after the music upstream stalled or failed, surfacing as 502, empty responses, HTML error pages, and fetch timeouts. Music is a companion feature for the generated story, so recommendation failures must not block gameplay or turn into global API failures.

## What Changes

- Add an API-level degradation contract for `/api/music/recommend`.
- Enforce a bounded route timeout around story-to-music analysis.
- Return a valid empty recommendation with safe instrumental `music_brief` defaults when the upstream recommendation path times out or errors.
- Preserve legacy response compatibility for music items or recommendation objects that do not expose newer optional fields.
- Register the new contract tests in `test.sh`.

## Impact

- Backend music API: `src/api/routers/music.py`.
- Test gate: `test.sh`.
- Contract tests: `tests/test_music_recommend_api_degradation_contract.py`.
