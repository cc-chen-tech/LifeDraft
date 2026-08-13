## Why

Entity collection can lose story characters, surface false positives, or block
the UI after a successful add. A provider-free reliability suite already covers
these regressions but is not part of the maintained gate.

## What Changes

- Promote verified entity recognition and collection-refresh contracts to both
  maintained backend workflows.
- Preserve the current coverage floor unless two complete runs justify a
  higher threshold.

## Capabilities

### New Capabilities
- `entity-collection-reliability-gate`: Maintained coverage of deterministic
  entity recognition and collection refresh regressions.

### Modified Capabilities
- `test-gates`: Both maintained workflow selections include entity collection
  reliability contracts.

## Impact

- Affected test surface: entity recognition, collection router fields, and
  frontend collection refresh behavior.
- No production behavior or existing test content is changed.
