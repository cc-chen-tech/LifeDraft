## Why

NPC continuity validation is a high-risk post-generation guard, but its
maintained coverage is only about 9 percent. Existing tests sit in a
conditionally skipped omnibus file, so they do not form a stable gate.

## What Changes

- Add direct, provider-free contracts for NPC appearance, behavior, identity,
  and personality contradictions.
- Promote only the twice-stable suite to maintained workflows.

## Capabilities

### New Capabilities
- `npc-attribute-contract-coverage`: Stable contracts for NPC profile
  continuity validation.

### Modified Capabilities
- `test-gates`: Maintained workflows run the stable NPC attribute contracts in
  matching order.

## Impact

- Adds tests only; no production behavior changes.
