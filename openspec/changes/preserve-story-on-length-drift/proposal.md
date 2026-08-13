## Why

Production expert stories are routinely complete and readable while exceeding the
current 800-1200 character target. The round generator currently promotes that
soft target to a terminal validity gate, clears the last usable story after a
consistency rewrite, and can therefore return no story or options for otherwise
good 1329-2315 character output.

## What Changes

- Treat target-length and paragraph-shape findings as diagnostics and optional
  repair signals, never as the sole reason to erase usable prose.
- Preserve the latest complete, locally valid story across repair exhaustion and
  generate contextual fallback options when later provider work fails.
- Limit Harness terminal rejection to severe continuity violations; presentation
  and shape findings remain observable but non-terminal.
- Make consistency rewrites inherit the current quality-level token budget.
- Remove the global test fixture that silently disables the production Harness
  path and cover both enabled and disabled configurations explicitly.

## Capabilities

### New Capabilities

- `soft-narrative-length-recovery`: Complete narrative prose remains usable when
  it drifts from product length targets, with contextual option recovery.

### Modified Capabilities

- `gameplay-generation-recovery`: Harness terminal failures are restricted to
  severe continuity violations and recovery retains the latest usable prose.

## Impact

Changes are confined to round-story recovery, consistency-rewrite budgeting,
Harness terminal classification, and their contracts. The unified budget model,
new product target bands, option UI, input limits, summaries, and long-context
compaction remain separate follow-up changes.
