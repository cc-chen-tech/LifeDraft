## Context

The generator has four distinct checks after a provider returns prose: local
consistency, target length/paragraph shape, AI consistency, and the Harness.
Historical fixes collapsed these checks into one validity concept. In particular,
`story_too_long`, `story_too_short`, and `over_fragmented_paragraphs` prevent a
candidate from entering `best_valid_story_text`, and post-consistency shape drift
explicitly empties that variable. A later retry or option-provider failure then
has nothing to recover.

## Goals / Non-Goals

**Goals**

- Keep non-empty, complete, locally valid prose available despite target drift.
- Preserve rejection for blank output, repeated committed prose, and severe
  continuity contradictions.
- Return the latest usable prose with three contextual fallback options when
  later provider work is exhausted.
- Use the active quality-level output-token budget for consistency rewrites.
- Exercise both production Harness configurations without a global environment
  override.

**Non-Goals**

- Introduce the final `NarrativeBudget`/call-tracker architecture.
- Change the requested length bands or total deadlines in this change.
- Redesign generated option text or the option-card UI.

## Decisions

### Length and paragraph shape are diagnostics

The existing validator continues to report target drift. One bounded repair may
still be attempted where the current quality path allows it, but the repair result
is not rejected solely for the same drift and the previous usable candidate is
not erased.

### Recovery tracks the latest usable prose

A candidate becomes recoverable after it is non-empty and passes the local quick
validator. Repeated committed prose and severe Harness failures roll recovery back
to the previous candidate. Later length drift, option failure, timeout, or provider
exhaustion returns the latest remaining candidate with contextual fallback options.

### Harness terminal failures use an allowlist

Only critical failures representing continuity corruption can deny final
availability: unavailable/fabricated entities or facts, era contradictions,
world-model position/commitment violations, and temporal, state, item, spatial,
attribute, information-barrier, or cause-effect contradictions. Other Harness
findings remain diagnostic and do not consume terminal retries.

### Consistency repair inherits the active quality budget

`_validate_and_retry_story` resolves the current quality-level generation budget
and passes its `max_tokens` to the repair call. The fixed 8192 value is removed.
The later unified-budget change will replace this compatibility boundary.

## Risks / Trade-offs

- Softening target drift can expose longer prose. This is intentional; later
  display and compression budgets will improve presentation without data loss.
- A deterministic Harness allowlist must remain synchronized with new severe
  continuity constraint types. Contract tests lock the current classification.
- Removing the global test override can reveal tests that depended on ambient
  environment. Relevant generation contracts set Harness state explicitly.

## Rollback

Revert this change to restore strict shape gating. No schema or persisted data is
changed.
