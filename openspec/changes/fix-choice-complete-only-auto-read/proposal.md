## Why

Live testing reported that story voice reading did not start after the player
made a choice. The current happy-path tests covered streamed `story` chunks, but
the choice SSE endpoint can also finish with only a `complete.event_description`
payload. In that path the frontend moved to the result phase without writing the
final choice story into `storyText`, so the sound console had no completed
choice text to auto-read.

## What Changes

- Treat `complete.event_description` from choice SSE as authoritative fallback
  story text when no streamed story chunk has already written the same text.
- Preserve existing streamed behavior by avoiding duplicate appends when
  `storyText` already contains the complete payload.
- Add hook-level regressions for complete-only choice streams and the
  `usePlayGame` story state that feeds the unified sound console.

## Impact

- `frontend/src/hooks/game/choiceUtils.ts`
- `frontend/src/__tests__/hooks/useChoiceHandler.test.ts`
- `frontend/src/__tests__/hooks/usePlayGame.phase.test.ts`
