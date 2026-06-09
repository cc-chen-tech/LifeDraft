## Design

`ChatBar` currently stores summary results as assistant chat messages and expands `chat-bar-panel` when the collapsed "人生总结" quick action is clicked. The fix introduces summary-specific component state so the same `/api/games/{id}/summary` endpoint can be used without showing chat history or the chat input.

The component will maintain a dedicated summary panel state:

- `isSummaryOpen`: controls visibility of the summary panel.
- `lifeSummary`: stores the latest generated summary content and week range.
- `lifeSummaryError`: stores a user-visible failure message.

Clicking "人生总结" opens the summary panel and starts generation. It must not call `setIsExpanded(true)`. The expanded chat quick action can also reuse the same summary panel so both entry points have consistent behavior.

The summary panel is a compact fixed bottom-right surface with `data-testid="life-summary-panel"` and a close button. It intentionally omits the chat input placeholder `向剧情助手提问` and the `chat-bar-panel` test id so browser and unit tests can distinguish it from the story assistant.

## Alternatives Considered

- Keeping summary inside chat history but changing the title was rejected because the report is specifically about the summary action opening the story assistant dialog.
- Replacing the collapsed summary button with only a chat command was rejected because the control is already exposed as a first-class quick action.

## Risks

- The component already has several overlay states. The implementation should keep this scoped to summary state and avoid changing rewrite or normal chat behavior.
