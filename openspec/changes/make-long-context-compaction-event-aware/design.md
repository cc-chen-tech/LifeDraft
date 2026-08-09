## Context

The raw append-only round history is the source of truth. Long-context snapshots are derived prompt artifacts used only when the DeepSeek input prefix approaches its budget. The existing v1 artifact validates a declared prefix digest but can character-trim the corresponding content, creating false coverage.

## Decisions

### Snapshot v2 records exact whole-event coverage

Schema v2 preserves `snapshot_id`, `start_event_id`, `end_event_id`, `source_digest`, `content`, and `token_count`, and adds `covered_event_ids`. Entries are serialized and admitted one at a time. The source digest covers exactly that contiguous list. No entry is sliced after admission.

### Raw history remains authoritative

Compaction replaces only a contiguous prefix whose complete entries fit. The renderer starts raw history immediately after the final covered event. If no complete entry fits, it writes no snapshot and retains every event raw, even when a deliberately tiny test budget cannot satisfy the hard cap.

### Ledger enrichment is source linked

When `ENABLE_STRUCTURED_STORY_MEMORY` is enabled, canonical events use a matching continuity-ledger timeline entry for its summary, choice, effects, and source event identity. Missing or uncertain ledger fields fall back to deterministic raw round data. A snapshot never invents a source ID or marks a non-matching ledger entry covered.

### v1 is rebuilt lazily

Loading a save performs no migration. When the builder encounters a valid v1 snapshot, it renders from raw history and rebuilds v2 only if compaction is required. Invalid or stale derived snapshots are discarded without modifying raw events.

### Dynamic request parts have explicit priority

The builder accepts structured request parts ordered as current request, character authority, ledger facts, recent events, and old history. The first three are required. Optional recent and old parts are admitted only when complete. If the required parts alone exceed 800,000 input tokens, the builder raises `LongContextBudgetError`; history pressure alone never causes that error.

## Compatibility and rollback

V2 is additive and retains all v1 fields. The previous compatible release can ignore `covered_event_ids` and still validate the v1 fields. No database migration runs and raw round history is never deleted, so rolling back may rebuild a v1 derived snapshot without losing events.

## Fixed budgets

- Absolute input limit: 800,000 tokens.
- Snapshot target: 12,000 tokens.
- Dynamic reserve: 80,000 tokens.
