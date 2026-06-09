## 1. Tests First

- [x] 1.1 Add an API contract test proving `TimeoutError` from music analysis returns HTTP 200 with an empty playable list and safe fallback brief.
- [x] 1.2 Add an API contract test proving a slow upstream analysis is cut off by a route-level timeout.
- [x] 1.3 Register the new contract tests in `test.sh`.

## 2. Implementation

- [x] 2.1 Add a safe fallback `MusicRecommendationResponse` for degraded recommendations.
- [x] 2.2 Wrap `analyze_story_for_music` in a bounded `asyncio.wait_for`.
- [x] 2.3 Preserve normal recommendation compatibility when optional `source` or `music_brief` fields are absent.

## 3. Verification

- [x] 3.1 Verify the new tests fail before implementation.
- [x] 3.2 Run focused music router and music recommendation tests.
- [x] 3.3 Run `./test.sh contract`.
- [x] 3.4 Run full `./test.sh all`.
