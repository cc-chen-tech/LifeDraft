# 2026-06-09 Opening Story Truncated Complete Event

## Summary

Production QA on `story101.live` found a new opening-story display failure while creating a fresh modern Shanghai character after deploying `99d297e3`.

The opening story streamed and then appeared to complete, but the final paragraph ended mid-sentence:

> 林知夏笑了，正要回复，刘子涵推

Evidence:

- Screenshot: `docs/screenshots-2026-06-09-heartbeat/opening-story-truncated-lin-zhixia.png`
- Production route: `https://story101.live/story/opening`
- Character: `林知夏`

## Root Cause

The normal `AIClient.call(..., stream_callback=...)` path can inspect `finish_reason` and run truncation recovery. The opening-story endpoint uses `CharacterCreator.generate_opening_story`, which returns a raw provider stream. The API router assembles `full_text_holder` from streamed chunks and emitted `complete` as long as the text was non-empty.

That meant a long story ending in an incomplete Chinese sentence could be cached and sent to the frontend as a successful `complete` event.

## Regression Test

- `tests/test_opening_story_contract.py::TestOpeningStoryAPIContract::test_opening_story_truncated_text_does_not_emit_complete_or_cache`

The test verifies that a sufficiently long Chinese opening-story fragment ending without terminal punctuation emits an SSE `error` event, does not emit `complete`, and is not cached as a valid result.

## Fix

- `src/api/routers/character.py`
  - Captures raw stream `finish_reason`.
  - Adds `_opening_story_appears_truncated`.
  - Treats `finish_reason == "length"` or a sufficiently long Chinese story ending without terminal punctuation as a truncation failure.
  - Clears the cached result and emits `Opening story appears truncated` instead of sending a false `complete` event.

## Verification

- `pytest tests/test_opening_story_contract.py -q`
- `pytest tests/test_opening_story_contract.py tests/test_gate_gameplay_behavior_no_mock.py tests/test_character_settings_api_contract.py tests/test_api_games.py -q`
- `./test.sh preflight`
- Pushed `main` to `origin/main`.
- GitHub Actions for the pushed commit failed before usable runner logs were available: `gh run view --log-failed` returned `log not found`, so this remains classified as a platform runner/check blocker rather than a code failure.
- Deployed the pushed commit to ECS `/opt/story2`.
- Verified production health:
  - `https://story101.live/api/health` returned `{"status":"ok","active_sessions":0}`.
  - `https://story101.live/` returned `HTTP/1.1 200 OK`.

Status: fixed, pushed, manually deployed to ECS, and production health verified.
