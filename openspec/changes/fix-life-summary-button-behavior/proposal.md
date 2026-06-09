## Why

The 2026-06-08 UX report found that clicking "人生总结" opens the "剧情助手" chat panel, including the assistant input, instead of behaving like a dedicated summary action. This makes the summary control indistinguishable from chat and repeats an older P1 interaction bug.

## What Changes

- Treat "人生总结" as a dedicated summary surface, not as a shortcut that opens the chat assistant.
- Keep the summary API call behavior, but render the generated summary in a summary-specific panel with its own title and loading/error states.
- Add a regression test proving the collapsed "人生总结" action does not render the chat assistant panel or input.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `gameplay-side-controls`: Add a requirement that the life summary action opens a dedicated summary UI rather than the story assistant chat panel.

## Impact

- Frontend `ChatBar` behavior and tests.
- No backend API, database schema, or generated type changes.
