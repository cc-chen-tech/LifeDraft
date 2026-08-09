## Why

Scene prompts must name every in-story character with compatible appearance
data. The local extraction and manifest path is provider-free but undercovered.

## What Changes

- Add no-mock contracts for player/NPC extraction, duplicate prevention,
  structured-field compatibility, manifest positions, and era normalization.
- Add the suite to both maintained workflows.

## Capabilities

### New Capabilities

- `scene-character-manifest-contract-gate`: Maintained coverage for pure scene
  character prompt preparation.

### Modified Capabilities

- None.

## Impact

- `tests/test_scene_character_manifest_contracts.py`
- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
