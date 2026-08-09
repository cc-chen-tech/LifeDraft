## Why

Opening illustration generation persists user-visible state, but the maintained suite does not cover replacement, reference-image selection, or regeneration metadata as one lifecycle.

## What Changes

- Add deterministic database-backed contracts for opening-illustration creation and replacement.
- Cover current-illustration reference priority, player-image fallback, and persisted regeneration metadata.
- Include the new test module in both maintained backend workflow lists.

## Capabilities

### New Capabilities
- `opening-illustration-lifecycle-contracts`: Maintained coverage for the opening illustration generation and regeneration lifecycle.

### Modified Capabilities

- None.

## Impact

- Test and workflow-list changes only; no production image, database, or API behavior changes.
