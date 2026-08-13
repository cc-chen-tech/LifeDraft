## Why

The image router exposes browser-visible file delivery and scene-image event behavior, but its maintained coverage emphasizes database reads rather than local bytes, SSE payloads, and authorization failures. These provider-free boundaries can catch delivery regressions before browser-agent testing.

## What Changes

- Add real local-storage contract tests for image-file response bytes, content types, and cache headers.
- Add real database contract tests for image and game ownership failures.
- Add a cached scene-image SSE contract that validates the client-facing event payload.
- Register the new test module in both maintained backend workflow lists.

## Capabilities

### New Capabilities

- `images-local-delivery-contracts`: Maintained tests that preserve local image delivery, image-event payload, and ownership boundaries.

### Modified Capabilities

- None.

## Impact

Affected test coverage is limited to `src/api/routers/images.py`, local image storage behavior, and the maintained test lists in the backend workflows. No production API behavior or external dependencies change.
