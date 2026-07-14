## Why

The image provider boundary is high risk: a request-shape or response-handling regression breaks scene and character images even when pure payload helpers still pass. Maintained coverage currently exercises helpers but not enough of the real HTTP lifecycle without external provider access.

## What Changes

- Add deterministic loopback-only MiniMax provider contracts for text generation, image editing, URL downloads, and typed provider failures.
- Add the new contract file to both maintained backend workflow selections.

## Capabilities

### New Capabilities

- `local-minimax-provider-contracts`: The maintained gate validates MiniMax HTTP behavior against an in-process loopback server.

### Modified Capabilities

- `test-gates`: The maintained backend gate includes deterministic provider-boundary coverage without external network or provider credentials.

## Impact

- `tests/test_local_minimax_provider_contracts.py`
- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
- Maintained backend coverage measurement
