# Fix Choice Complete Text Ownership

## Why

Choice SSE streams append visible story text through `onStory`. The completion
callback later receives summary and state fields, but current main also used
`story_continuation` from the complete payload to call `setStoryText` again.
That makes successful streams vulnerable to duplicate story appends or late
overwrites after retry.

## What Changes

- Keep choice story text ownership with streaming `onStory`.
- Preserve the existing complete-only fallback when an SSE stream ends without
  any story chunks.
- Keep explicit fallback and round-history recovery paths as the only non-stream
  paths that can replace recovered choice text.
- Make `handleChoiceComplete` update completion state, summaries, result phase,
  current event cleanup, and follow-up sync only.
- Add regression coverage that `handleChoiceComplete` payloads with
  `story_continuation` or `event_description` do not mutate visible story text.

## Impact

- Frontend choice-completion behavior only.
- No backend API, OpenAPI schema, or persistence change.
