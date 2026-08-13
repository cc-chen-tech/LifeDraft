## Why

Character-creation era alignment, placeholder-name cleanup, and rule-based
attributes set the initial state for every game, yet the 429-statement module
has only 9.56 percent maintained coverage. Existing coverage relies heavily on
mocked AI generators, while the deterministic normalization paths can be
verified directly.

## What Changes

- Add provider-free contracts for life-vision era alignment and family-name
  normalization.
- Add rule-based initial-attribute and formatting contracts using an unbound
  `CharacterCreator` helper instance.
- Promote only twice-stable tests to both maintained workflows and ratchet the
  integer floor only when repeatable evidence allows it.

## Capabilities

### New Capabilities
- `character-creation-contract-coverage`: Deterministic contracts for initial
  character setting normalization and rule-based attributes.

### Modified Capabilities
- `test-gates`: Maintained backend workflows run the stable character-creation
  contract suite in matching order.

## Impact

- Adds tests for pure helpers in `src/game/character_creation.py`.
- Updates maintained test lists and, only if proven, the coverage floor.
- Leaves production code and existing tests unchanged.
