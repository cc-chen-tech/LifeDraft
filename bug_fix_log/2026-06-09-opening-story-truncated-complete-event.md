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

- `tests/test_opening_story_contract.py::TestOpeningStoryAPIContract::test_opening_story_length_finish_reason_truncation`

This additional regression verifies `finish_reason == "length"` (common provider truncation signal) is treated as failed generation and also leaves cache `result` empty.

## Fix

- `src/api/routers/character.py`
  - Captures raw stream `finish_reason`.
  - Adds `_opening_story_appears_truncated`.
  - Treats `finish_reason == "length"` or a sufficiently long Chinese story ending without terminal punctuation as a truncation failure.
  - Clears the cached result and emits `Opening story appears truncated` instead of sending a false `complete` event.

## Verification

- `pytest tests/test_opening_story_contract.py -q`
- `./test.sh mypy`
- `./test.sh imports`
- `./test.sh contract`
- `./test.sh db`
- `./test.sh e2e`
- `./test.sh preflight`
- `./test.sh preflight`（includes OpenSpec、前置门禁、前端静态检查、关键 Jest 回归）

Observed: all listed command layers passed locally in this environment.

- `./test.sh e2e` passed with 303+ core/browser tests and 4+专项 suites:
  - `core`: 303 tests
  - `e2e/story-voice-reading.spec.ts`: 8/8
  - `e2e/minimax-story-audio-generation.spec.ts`: 4/4
  - `e2e/character-settings-persistence.spec.ts`: 1/1
  - `e2e/collection-panel-cache.spec.ts`: 5/5
  - `e2e/collection.spec.ts`: 22/22
  - `e2e/entity-recognition.spec.ts`: 27/27

Status: fixed locally with full layered verification.

Status: fixed in code, fully verified locally by preflight + e2e, and docs updated with latest test evidence.
