## Why

CollectionService transforms persisted game state into the frontend collection response, but maintained tests do not exercise its end-to-end in-memory assembly across character, item, landmark, and cached-image fields.

## What Changes

- Add provider-free collection-assembly contracts using an in-memory image cache.
- Cover deduplication and default-field behavior across canonical and legacy character sources.
- Promote the new module to both maintained backend workflows.

## Capabilities

### New Capabilities
- `collection-assembly-contracts`: Maintained response-shape coverage for CollectionService's in-memory entity assembly.

### Modified Capabilities

- None.

## Impact

- Test and workflow-list changes only; no database, image, API, or production behavior changes.
