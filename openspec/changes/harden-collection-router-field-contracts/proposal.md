## Why

Collection behavior combines structured character fields with the currently displayed story, and missing or duplicated entities were previously discovered late in browser flows. The maintained suite lacks direct, no-provider coverage of these router-level field and authentication boundaries.

## What Changes

- Add provider-free contracts for collection user requirements, session player-state access, and entity-name normalization.
- Add contracts for current-story recognition history and existing-description no-op paths.
- Register the new module in both maintained backend workflow lists.

## Capabilities

### New Capabilities

- `collection-router-field-contracts`: Maintained collection router contracts for identity, current-story, and no-op field semantics.

### Modified Capabilities

- None.

## Impact

Only tests and maintained workflow lists change. The coverage target is `src/api/routers/collection.py`; no collection API, database schema, or provider behavior is modified.
