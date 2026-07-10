## Context

The opening page currently treats the SSE `complete` event as both data completion and visual completion. `StreamingText` intentionally continues its typewriter animation after streaming stops, so the final payload can be complete while the visible paragraph still ends mid-sentence.

## Goals / Non-Goals

**Goals:**
- Report when `StreamingText` has visibly rendered its entire current text.
- Require both SSE completion and visible completion before navigation is enabled.
- Prevent stale completion callbacks from a previous text or retry from enabling the button.

**Non-Goals:**
- Waiting for illustration generation.
- Changing the backend opening-story stream.
- Removing or speeding up the typewriter effect.

## Decisions

1. Add an optional `onDisplayComplete(text)` callback to `StreamingText`. The component owns the displayed-length state and is the authoritative place to signal visible completion.
2. Deduplicate callback delivery per exact text value with a ref. Parent state updates must not trigger repeated completion effects.
3. The opening page stores `isDisplayComplete` separately from `isComplete`; retries and incoming chunks reset display readiness, and the start control requires both values.
4. Existing non-streaming consumers remain unchanged because the callback is optional.

## Risks / Trade-offs

- [A stale callback enables a newer attempt] -> Include the completed text in the callback and compare it with the current final story before setting readiness.
- [Callback loops during parent rerender] -> Track the last completed text in a ref and emit once per exact value.
- [Very long opening takes longer before navigation] -> Preserve the intended visible reading animation; illustration remains non-blocking.
