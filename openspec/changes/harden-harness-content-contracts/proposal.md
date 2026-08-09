## Why

Item continuity and deterministic narrative-hint functions are high-frequency generation safeguards, but the maintained gate does not yet cover them adequately. One existing validator suite is stable and no-double, while the existing narrative suite contains a mock-dependent case and cannot be promoted as-is.

## What Changes

- Promote the verified no-double standalone validator contract suite into both maintained workflows.
- Add new no-double contracts for item possession continuity and narrative structure, arc, world-event, and conflict hints.
- Measure the expanded gate twice and ratchet the coverage floor only if repeatable evidence permits it.

## Capabilities

### New Capabilities
- `harness-content-contract-coverage`: Deterministic contracts for inventory continuity and narrative-hint validation.

### Modified Capabilities
- `test-gates`: Maintained backend workflow selections include verified harness content contracts symmetrically.

## Impact

- Affects test-only files, maintained workflow selections, coverage threshold, and OpenSpec artifacts.
- Excludes production code and mock-dependent existing tests.
