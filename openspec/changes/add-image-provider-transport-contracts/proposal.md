## Why

Image-provider transport failures have user-visible recovery semantics, but their maintained coverage does not exercise edit safety handling, malformed responses, or download status mapping.

## What Changes

- Add provider-free transport boundary contracts using deterministic response and session fakes.
- Add the module to both maintained backend workflow lists.

## Capabilities

### New Capabilities
- `image-provider-transport-contracts`: Maintained typed-error contracts for MiniMax image transport boundaries.

### Modified Capabilities

- None.

## Impact

- Test and workflow-list changes only; no provider or production behavior changes.
