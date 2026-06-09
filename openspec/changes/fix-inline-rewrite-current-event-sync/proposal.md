## Why

The UX report found that the inline rewrite sheet could open and submit, but the story did not reliably behave as rewritten afterward. The frontend callback updated visible `storyText` only, leaving the active `currentEvent.story` unchanged. That makes later save/load, media handoff, option recovery, and current-event consumers continue to see the old story.

## What Changes

- Treat inline rewrite completion as a current-event mutation, not just a visible text replacement.
- Update `currentEvent.story` when the rewritten story becomes the current story.
- Add a PlayPage regression test that drives the inline rewrite sheet through the SSE complete path and asserts both `setStoryText` and `currentEvent.story` update.

## Capabilities

### Modified Capabilities
- `gameplay-side-controls`: Inline rewrite completion keeps visible story text and current event state in sync.

## Impact

- Frontend PlayPage rewrite completion handler.
- Frontend PlayPage regression coverage.
