## Why

Relationship-person generation defines the initial social state of a game, but its
field-compatibility and recovery behavior is not covered by the maintained
backend gate. Regressions here currently surface late in browser-driven play.

## What Changes

- Add deterministic maintained tests for relationship-description compatibility
  and required default fields.
- Add deterministic maintained tests for invalid relationship retries and the
  complete fallback shape after repeated invalid responses.
- Register the new test module in both maintained backend workflow lists.

## Capabilities

### New Capabilities
- `relationship-person-recovery-contracts`: Maintained provider-free contracts
  for generated relationship-person compatibility and recovery behavior.

### Modified Capabilities

- None.

## Impact

Adds a test module and CI workflow entries only. Production character-creation
behavior and existing tests remain unchanged.
