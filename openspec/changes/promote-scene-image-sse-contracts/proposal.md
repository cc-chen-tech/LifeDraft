## Why

Scene-image updates reach the frontend through an authenticated SSE endpoint. Its existing contract suite verifies user isolation and ready/failed event payload fields using the real API and database, but it is not selected by the maintained backend gate.

## What Changes

- Add the existing scene-image SSE contract suite to both maintained backend workflows.
- Preserve ordered workflow-list parity and retain the coverage floor unless measurement supports a higher integer.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `test-gates`: The maintained backend gate covers scene-image SSE authentication, ownership, and client-visible payload contracts.

## Impact

- Affects `.github/workflows/backend-tests.yml` and `.github/workflows/coverage.yml` only.
- Uses the existing real HTTP/database suite `tests/test_scene_image_sse_contract.py`.
- Does not change production code, APIs, database schema, or frontend behavior.
