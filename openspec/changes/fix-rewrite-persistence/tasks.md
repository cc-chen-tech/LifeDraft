## 1. Reproduce

- [x] Add a failing streaming rewrite test proving `player_state.current_event_data` remains old after rewrite.
- [x] Add a failing non-streaming rewrite test proving persisted event data remains old after rewrite.

## 2. Fix

- [x] Add shared rewrite persistence helper.
- [x] Use the helper from `stream_rewrite`.
- [x] Use the helper from `/api/games/{game_id}/rewrite`.

## 3. Verify

- [x] Run targeted red tests before implementation.
- [x] Run `pytest tests/test_sse_helpers.py::TestStreamRewrite tests/test_api_story.py::TestRewriteStory -q`.
- [x] Run focused frontend rewrite tests for PlayPage, ChatBar, and SSE parsing.
- [x] Run `npx openspec validate fix-rewrite-persistence --strict`.
