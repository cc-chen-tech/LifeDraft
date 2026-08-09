## Context

The runtime already persists a source-linked `ContinuityLedger`, but display prose is generated through both `SummaryGenerator` and three standalone generator classes. Length requirements and failure behavior therefore drift. This change consolidates display output without changing existing stored schemas.

## Decisions

### Display budgets are localized information budgets

Use Chinese Unicode characters and English words. Soft target bands are week 80-160 / 50-100, month 180-320 / 120-220, year 350-600 / 220-400, and life 500-900 / 320-600. Compression begins above each target maximum and preserves whole sentences.

### Display prose is not model authority

Display summaries remain in existing response and save fields for users and compatibility. Prompt memory continues to derive identity, timeline, facts, relationships, and commitments from `ContinuityLedger`. A display call may fail without rolling back a committed event or its ledger entry.

### Compatibility wrappers delegate

`WeeklySummaryGenerator`, `MonthlySummaryGenerator`, and `YearlySummaryGenerator` retain their public constructors and result dictionaries for one release. They assemble their existing metadata but delegate natural-language generation and normalization to `SummaryGenerator`.

### Compaction never invents coverage

Sentence-aware compaction selects complete sentences that fit the configured threshold. If the first sentence alone is too large, it returns that complete sentence rather than cutting it; absolute request limits are handled elsewhere.

## Non-goals

- No long-context snapshot schema change; that is the following `make-long-context-compaction-event-aware` change.
- No database migration or deletion of legacy summaries.
- No frontend redesign.
