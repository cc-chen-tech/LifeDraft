## Why

Character image generation is a high-risk user-visible workflow, yet its
deterministic contract suite is outside the maintained gate. The suite uses a
real database session and hand-written provider/storage fakes, so it can catch
persisted image regressions without external provider availability.

## What Changes

- Promote the verified character image service contract file to both maintained
  workflow selections.
- Keep threshold changes dependent on two full coverage measurements.

## Capabilities

### New Capabilities
- `character-image-service-gate`: Maintained coverage of deterministic
  character image generation and persistence contracts.

### Modified Capabilities
- `test-gates`: Both maintained workflow selections include the verified
  character image service contract file.

## Impact

- Affected source under test: `src/services/image/character_service.py`.
- No provider call, production behavior, or existing test content changes.
