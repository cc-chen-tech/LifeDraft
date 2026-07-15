## Why

When story generation fails, the fallback is the player-visible recovery path.
Its locale-specific structure and use of established setting data need stable
coverage in the maintained backend suite.

## What Changes

- Add provider-free tests for Chinese and English fallback stories.
- Verify era, traits, relationship anchors, and invalid round-number handling.
- Register the new test module in both maintained backend workflows.

## Capabilities

### New Capabilities
- `story-generator-fallback-shape-contracts`: Maintained contracts for
  player-visible story-generation fallback shape and grounding.

### Modified Capabilities

- None.

## Impact

Adds tests, CI workflow entries, and OpenSpec artifacts only; production story
generation and existing test modules are unchanged.
