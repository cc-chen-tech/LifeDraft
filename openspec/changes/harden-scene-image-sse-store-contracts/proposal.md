## Why

Scene-image generation reaches the UI asynchronously through EventSource.
Existing tests cover fetch and polling, but do not protect the store's SSE
ready, terminal-failure, heartbeat, and connection replacement behavior that
has previously required browser-agent diagnosis.

## What Changes

- Add deterministic Jest contracts for scene-image SSE state transitions.
- Cover ready replacement by scene key, terminal failure state, heartbeat
  no-op behavior, and subscription cleanup.

## Capabilities

### New Capabilities
- `scene-image-sse-store-contracts`: Store-level contracts for asynchronous
  scene-image event delivery.

### Modified Capabilities

- None.

## Impact

Affected code is a new Jest test file for `useSceneImageStore` plus OpenSpec
documentation. The production EventSource and image API behavior is unchanged.
