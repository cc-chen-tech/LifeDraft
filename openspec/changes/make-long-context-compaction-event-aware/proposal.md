## Why

The current long-context snapshot declares an event range and digest before shortening its content one character at a time. A snapshot can therefore claim that an event is covered while retaining only a fragment, and the final hard-cap fallback can discard every raw event. This makes long-running saves vulnerable to silent history loss.

## What Changes

- Introduce a backward-compatible snapshot schema v2 that keeps the v1 fields and adds the exact `covered_event_ids` written as complete entries.
- Build snapshot entries from source-linked continuity-ledger timeline data, choices, effects, and raw event identity, packing only whole events.
- Keep every event that does not fit a snapshot as a raw event; make `end_event_id` equal the final event actually packed.
- Treat v1 snapshots as derived compatibility data and rebuild them lazily without migrating or truncating saved raw history.
- Budget dynamic context by explicit priority: current request, character authority, ledger facts, recent events, then old history.
- Raise an explicit technical budget error only when required current-request context alone exceeds the absolute input limit.

## Impact

- Backend: `LongStoryContextBuilder`, snapshot validation/rendering, and structured dynamic-context budgeting.
- Persistence: derived snapshots may be rewritten to schema v2 on use; `round_history` and existing save schemas are not migrated.
- Compatibility: v1 and v2 saves both load, continue, and can be read by the preceding compatible release because all v1 fields remain present.
- Tests: whole-event coverage, v1 lazy rebuild, priority trimming, 600-event stress, and save/restore continuation.
- Rollout: stacked after `separate-display-summary-memory` and guarded by `ENABLE_STRUCTURED_STORY_MEMORY` for authoritative ledger-enriched entries.
