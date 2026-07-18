## Why

Image selection and state restoration sit on the front-end/back-end field boundary: an invalid explicit image reference must not leak across games, while saved game state must preserve the character settings used for later image work. These deterministic persistence branches are not represented in the maintained backend suite.

## What Changes

- Add real SQLite and local-file contracts for active image selection, primary-image fallback, compressed data-URL references, and saved character-setting recovery.
- Register the test module in both maintained backend workflow lists.

## Capabilities

### New Capabilities
- `image-service-persistence-contracts`: Provider-free ImageService contracts for persisted image and game-state fields.

### Modified Capabilities

- None.

## Impact

- Adds one test module for `src/services/image_service.py` using disposable database and file-storage state.
