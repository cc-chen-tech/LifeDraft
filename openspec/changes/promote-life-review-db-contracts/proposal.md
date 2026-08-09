## Why

The life-review response is a user-visible end-of-game summary. Its existing
real-state tests are stable and provider-free but not included in maintained
coverage.

## What Changes

- Promote the verified life-review and achievement contract suite to both
  maintained backend workflows without modifying the test itself.

## Capabilities

### New Capabilities

- `life-review-db-contract-gate`: Maintained coverage for generated life-review
  response data derived from player state and achievements.

### Modified Capabilities

- None.

## Impact

- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
