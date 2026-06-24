## 1. Tests

- [x] Add a regression where `/choice` SSE completes with `event_description` but no `story` chunks.
- [x] Add a `usePlayGame` regression proving the complete-only choice story updates `storyText`.
- [x] Run related voice, play page, and choice hook tests.

## 2. Fix

- [x] Write complete-only choice story text back into the current story state.
- [x] Avoid duplicating text when the streamed story chunks already populated `storyText`.

## 3. Verify

- [x] Run targeted frontend unit tests for choice handling, play-page voice readiness, and story voice controls.
