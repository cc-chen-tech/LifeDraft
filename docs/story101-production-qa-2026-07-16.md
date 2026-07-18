# Story101 Production QA - 2026-07-16

## P1: Choice continuation misclassified player grammar as new cast

- Reproduced on production after a Week 1 choice: a continuation using the player
  name in normal Chinese grammar (for example, `陈越把` and `陈越的`) and timeline
  prose (`时间上`) exhausted the cast-drift retry budget and returned an SSE error.
- The quick validator now treats the configured player name as an allowed person and
  ignores the timeline prefix. The regression contract verifies that the continuation
  completes on the first generation while the existing unfamiliar-cast checks remain.

## P1: Choice continuation blocked by first-person validation

- Reproduced on production after the first Week 1 choice: the second quick-validation
  attempt contained first-person text and the SSE stream returned an error instead of
  progressing the game.
- Fixed in `8622b7b2`: a second attempt with only the perspective diagnostic is kept,
  while all other quick-validation failures remain blocking.
- Production replay selected `陪她去书店再赴会` and reached the completed Week 1
  summary and `进入周中` without the former SSE error.

## P2: Generated music playlist ID rejected

- Production replay emitted a `422` for `PUT /api/music/playlist/{game_id}` because
  generated tracks use stable `ai-generated-<asset_id>` string IDs while the request
  contract accepted only integers.
- The playlist subsequently reloaded, but the failed request created avoidable console
  noise and could leave a local fallback state under worse network conditions.
- The API contract now accepts both standard numeric catalog IDs and generated string
  IDs. `test_put_playlist_accepts_generated_music_string_id` preserves this boundary.
