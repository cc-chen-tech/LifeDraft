## Why

Image generation is a high-risk provider boundary with low maintained coverage. Its protocol-normalization and error-classification helpers are deterministic but currently rely on provider integration tests that cannot enter the no-mock maintained gate.

## What Changes

- Add a new provider-free image-generator contract suite for URL normalization, MiniMax payload construction, image-source parsing, base64 validation, and typed provider errors.
- Add that new suite to both maintained backend workflows in the same order.
- Raise the coverage floor only if the measured expanded suite supports the next integer.

## Capabilities

### New Capabilities

- `image-generator-pure-contracts`: Deterministic contract coverage for image-provider request and response normalization without network calls.

### Modified Capabilities

- `test-gates`: The maintained backend gate covers image-generator protocol safety and error semantics without external providers.

## Impact

- Adds one test file and updates the two maintained workflow selections.
- Does not change production code, API behavior, provider configuration, or frontend behavior.
