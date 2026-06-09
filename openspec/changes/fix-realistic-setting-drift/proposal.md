## Why

The 2026-06-08 UX report found that an ordinary modern 28-year-old character drifted into "夜之城", "荒坂集团", and "赛博朋克 2077". This is a setting-authority failure: realistic modern settings must not be silently replaced by external sci-fi IP worlds.

## What Changes

- Add prompt-level hard constraints for realistic modern settings that forbid cyberpunk/future-world drift unless the player explicitly requested that genre.
- Explicitly prohibit introducing known external IP worlds, factions, or proper nouns such as "夜之城", "荒坂集团", and "Cyberpunk 2077" from generic modern settings.
- Add runtime quick-validation coverage so generated modern stories that still contain unrequested cyberpunk/IP drift are rejected and retried before options are generated.
- Add no-mock prompt contract tests for story-only, round-event, and opening-story prompts.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `story-display-quality`: Realistic modern story prompts must preserve the user-provided world boundary and forbid unrequested cyberpunk/IP-world drift.

## Impact

- Prompt helper constraints, quick validator constraints, and no-mock generation retry contract tests.
- No API, database schema, or frontend behavior changes.
