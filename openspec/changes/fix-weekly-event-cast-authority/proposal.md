# Fix Weekly Event Cast Authority

## Why

The round-event, story-only, choice-result, and scheduled-event prompts already
inject preset key-people authority constraints. The legacy weekly event prompt
still only listed available people and "do not invent new people" rules. That
made this path weaker than the rest of story generation and left room for the
original P0 drift: preset mentor/friend/peer relationships could be replaced by
a newly invented cast while technically not violating a strong required-cast
block because that block was absent.

## What Changes

- Inject `build_required_cast_constraints` into weekly event prompts.
- Keep the existing available-people list and no-new-named-people rule.
- Add prompt contract coverage for the weekly event path.

## Impact

- Prompt text only.
- No API, persistence, or OpenAPI schema change.
