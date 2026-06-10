## Context

`ChatBar` owns the inline rewrite sheet and reports the completed rewritten story through `onRewriteComplete`. `PlayPage` previously handled that callback by calling `setStoryText(newStory)` only. The active event object remained unchanged in the event store.

## Goals / Non-Goals

**Goals:**
- Make the rewritten story authoritative for the current event.
- Preserve the existing inline rewrite UI and SSE route.
- Keep current options intact when only story prose changes.

**Non-Goals:**
- Change backend rewrite generation semantics.
- Add rewrite persistence endpoints beyond existing game save behavior.
- Redesign the ChatBar layout.

## Decisions

- Update the current event in the frontend event store after a successful inline rewrite.
- Preserve existing options by shallow-copying the current event and replacing only `story`.
- Keep the callback in PlayPage so ChatBar remains a reusable UI component that does not know about game store internals.

## Risks / Trade-offs

- If no current event is present, only visible story text is updated. That is acceptable for contexts without options/current event, and it avoids fabricating an incomplete event.
