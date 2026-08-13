## Why

Character-image requests must preserve caller-supplied provider parameters such
as negative prompts. The deterministic existing suite exercises this provider
boundary with handwritten fakes and newly covers 14 ImageGenerator statements
not reached by the maintained selection.

## What Changes

- Add `tests/test_character_image_extra_params.py` to both maintained backend
  workflow selections in identical order.
- Define the provider-parameter propagation contract and verification steps.
- Raise the maintained coverage threshold to 51% only after complete exact
  verification succeeds.

## Capabilities

### New Capabilities
- `character-image-extra-params-contract-gate`: Maintained regression coverage
  for preservation of image provider extra parameters in character generation.

### Modified Capabilities

- None.

## Impact

- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
- Existing `tests/test_character_image_extra_params.py` is promoted unchanged.
