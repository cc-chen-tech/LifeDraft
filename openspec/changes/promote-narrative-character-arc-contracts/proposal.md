## Why

The maintained backend coverage gate does not currently execute the
deterministic `CharacterArcEngine` contract suite, leaving phase progression
and narrative-style behavior outside its regression scope. The suite directly
exercises 64% of the module without mock frameworks or external dependencies.

## What Changes

- Add `tests/test_narrative_character_arc.py` to both maintained backend
  workflow selections in the same order.
- Document the maintained coverage and parity contract for character-arc
  behavior.
- Verify the direct suite, dependency scan, workflow parity, and full
  maintained coverage gate.

## Capabilities

### New Capabilities
- `narrative-character-arc-contract-gate`: Maintained regression coverage for
  character-arc creation, phase progression, style selection, constraints, and
  graceful degradation.

### Modified Capabilities

- None.

## Impact

- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
- Existing `tests/test_narrative_character_arc.py` is promoted without changing
  assertions or application code.
