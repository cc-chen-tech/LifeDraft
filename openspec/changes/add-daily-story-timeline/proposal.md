## Why

Story2 currently generates an event, then performs a second long-form generation after every choice before advancing one of three weekly rounds. This creates a slow and difficult-to-recover state machine, while rewrite can leave old options attached to replacement prose.

## What Changes

- **BREAKING** Replace the three-round weekly progression with an authoritative 672-day timeline backed by a real Gregorian start date.
- Make the opening story the first playable day and generate exactly one complete story plus options per day.
- **BREAKING** Resolve generated choices without narrative continuation, custom choices, intermediate result confirmation, or weekly-summary pages; automatically begin the next day.
- Make rewrite and regenerate atomically replace both prose and options using versioned current events.
- Store canonical day history, exact scheduled dates, and date-keyed scene images while retaining legacy-save and legacy-image read compatibility.
- Add a staged `ENABLE_DAILY_TIMELINE_V2` rollout and an idempotent legacy migration preview/apply tool.

## Capabilities

### New Capabilities
- `daily-story-timeline`: Gregorian daily progression, legacy migration, versioned event selection, and daily state API contracts.

### Modified Capabilities
- `gameplay-continuity`: Daily stories replace round continuations, custom choices, weekly result pauses, and prose-only rewrite behavior.
- `character-setting-continuity`: Character creation supplies the exact playable start date and the opening becomes day one.
- `history-review`: History and scene media are keyed by story day/date instead of round stage for daily games.
- `gameplay-side-controls`: Daily gameplay exposes rewrite/regenerate without a custom-choice or next-round control.

## Impact

The change affects player-state serialization, save restoration, scheduled events, generation prompts and budgets, choice/rewrite/regenerate APIs, scene-image persistence, generated OpenAPI types, character creation, `/play`, history/media stores, and backend/frontend/E2E regression suites. Existing v1 saves remain readable and are upgraded once to timeline v2; v2 saves are not downgraded.
