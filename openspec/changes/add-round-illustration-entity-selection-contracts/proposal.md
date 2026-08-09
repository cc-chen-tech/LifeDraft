## Why

Round illustration quality depends on selecting established people, repeated props, and places from story state. The maintained suite has only one happy-path assertion, leaving the selection rules that prevent missing or noisy references unprotected.

## What Changes

- Add provider-free contracts for repeated-item eligibility and malformed dynamic facts.
- Cover established-location priority, recurring-location fallback, character de-duplication, and bounded entity assembly.
- Include the new module in both maintained backend workflows.

## Capabilities

### New Capabilities
- `round-illustration-entity-selection-contracts`: Maintained contracts for scene-reference entity selection from narrative state.

### Modified Capabilities

- None.

## Impact

- Tests and maintained workflow lists only; no generation, model, API, or production behavior changes.
