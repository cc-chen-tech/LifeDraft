## Why

ImageService has low coverage in the data-normalization and persisted-state
helper paths that feed image generation. These branches can be verified without
calling an image provider.

## What Changes

- Add deterministic contracts for prompt description extraction, era and
  character-info normalization, and latest saved-week lookup.
- Promote the new suite to both maintained backend workflows after verification.

## Capabilities

### New Capabilities
- `image-service-data-helper-contract-gate`: Maintained coverage for provider-
  independent ImageService data preparation and DB state lookup.

### Modified Capabilities

- None.

## Impact

- `tests/test_image_service_data_helper_contracts.py`
- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
