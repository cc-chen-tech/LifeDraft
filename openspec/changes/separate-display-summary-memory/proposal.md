## Why

Story2 currently treats several natural-language summaries as both display copy and model memory. Multiple weekly, monthly, yearly, and compression implementations use conflicting size targets, and some paths shorten text by raw character slicing. That can leave half sentences while also allowing a display-generation failure to obscure what the continuity ledger actually knows.

## What Changes

- Make `ContinuityLedger` the authoritative model memory for chronology, facts, relationships, commitments, and source event IDs; keep user-visible summaries as recoverable display prose.
- Define localized display-summary budgets for week, month, year, and life summaries.
- Compress oversized display prose only at complete sentence boundaries; never use a raw `text[:N]` result as the stored summary.
- Route the legacy weekly, monthly, and yearly generator classes through the shared `SummaryGenerator` implementation while retaining their public return shapes for one compatibility release.
- Keep ledger commits independent from display-summary generation and retain deterministic choice/effect/source facts when optional model extraction fails.

## Impact

- Backend: summary budgets and sentence-aware compaction, shared summary generation entry points, compatibility wrappers, and ledger/display failure isolation.
- Persistence: no migration and no removal of existing summary fields; authoritative facts remain in the existing ledger.
- Tests: localized budget boundaries, sentence completion, wrapper delegation, independent failure/recovery, and legacy save continuation.
- Rollout: stacked after `make-input-limits-explicit`; guarded by `ENABLE_STRUCTURED_STORY_MEMORY` where model-memory reads change.
