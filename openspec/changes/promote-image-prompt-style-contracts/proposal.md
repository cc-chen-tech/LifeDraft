## Why

Image prompts must preserve character appearance and style across generated scenes, yet the maintained backend gate excludes stable tests for the pure local helpers that enforce those constraints. Promoting them gives early regression coverage without invoking an image provider.

## What Changes

- Add existing appearance-anchor contracts to both maintained backend workflows.
- Add existing prompt-enhancer persistence and rule contracts.
- Add existing style-manager palette and temporal-progression contracts.
- Retain ordered workflow parity and the existing coverage threshold.

## Capabilities

### New Capabilities
- `image-prompt-style-maintained-gate`: Require local image appearance, prompt enhancement, and style-management contracts in the maintained backend suite.

### Modified Capabilities

- None.

## Impact

Only workflow test lists change. The selected tests use temporary local storage and deterministic in-process logic, with no browser or image-provider calls.
