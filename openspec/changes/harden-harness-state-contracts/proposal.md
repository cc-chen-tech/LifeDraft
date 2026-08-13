## Why

Character state, commitments, and movement are core gameplay continuity rules, yet their existing aggregate tests can be skipped and are outside the maintained gate. Stable local contracts can detect these regressions before browser-level gameplay checks.

## What Changes

- Add no-double public contracts for character-state, commitment, and spatial validators.
- Cover clear invalid and permitted state transitions using concrete world-model state.
- Promote the verified suite symmetrically into maintained backend workflows and adjust the coverage floor only with repeated evidence.

## Capabilities

### New Capabilities
- `harness-state-contract-coverage`: Deterministic contracts for character state, commitments, and spatial movement validation.

### Modified Capabilities
- `test-gates`: Maintained backend workflows include verified state-continuity contracts at an evidenced coverage floor.

## Impact

- Affects test-only files, maintained backend workflow selections, coverage threshold, and OpenSpec documentation.
- Does not change production behavior, existing tests, providers, databases, or browser tests.
