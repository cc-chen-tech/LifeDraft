## Why

Story2 currently expresses narrative length, output-token limits, retry counts, and timeouts in several independent files. Those values conflict across opening, round, continuation, rewrite, regeneration, Harness, and truncation-recovery paths, so a repair call can silently escape the user's selected quality budget and prompt text can contradict runtime enforcement.

## What Changes

- Introduce one localized narrative budget model covering narrative kind, operation, length band, output tokens, provider-call allowances, and total deadline.
- Add a shared call tracker that every prose, validation, and recovery call must consume before reaching a provider.
- Migrate opening, round, continuation, full rewrite, segment rewrite, regeneration, consistency repair, and truncation recovery to the shared resolver.
- Format all narrative-length prompt instructions from the resolved budget and remove conflicting fixed length numbers from active prompt and style-manifest paths.
- Keep `generation_budget.py` as a one-release compatibility re-export while new code imports `src.ai.budgets`.
- Guard the new path with `ENABLE_UNIFIED_NARRATIVE_BUDGETS`, defaulting off for staged rollout.

## Capabilities

### New Capabilities

- `localized-narrative-budgets`: Defines product length bands, compression thresholds, absolute limits, token ceilings, call allowances, deadlines, operation inheritance, and Chinese/English measurement.
- `generation-call-accounting`: Defines single-request call consumption, deadline enforcement, and non-recursive truncation recovery across prose and validation operations.

### Modified Capabilities

- `gameplay-generation-recovery`: Recovery and consistency repair inherit the original request budget and return the latest complete narrative when their shared call or deadline budget is exhausted.

## Impact

The change affects `src/ai/generation_budget.py`, a new `src/ai/budgets.py`, story generation and rewrite services, truncation recovery, gameplay opening/round/continuation call sites, narrative prompt builders, style manifests, feature-flag settings, and their Python/contract tests. It does not change stored event schemas, option display behavior, input-validation limits, summary budgets, or long-history compaction.
