## Why

The pure image compressor has an existing deterministic real-PIL contract that covers all remaining utility branches but is not maintained.

## What Changes

- Promote `tests/test_image_compressor_db.py` into both maintained backend workflows.

## Capabilities

### New Capabilities

- `image-compressor-gate`: Maintained coverage validates image compression formats and errors.

### Modified Capabilities

- `test-gates`: The maintained gate includes image compressor contracts.

## Impact

- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
