## Why

Story continuation fallback text is user-visible when AI generation fails, but its choice and state-effect mapping is not covered by the maintained backend gate.

## What Changes

- Add deterministic Chinese and English fallback-continuation contracts to both maintained backend workflows.

## Capabilities

### New Capabilities

- `story-fallback-continuation-maintained-gate`: Require deterministic fallback continuation contracts in the maintained backend suite.

### Modified Capabilities

- None.

## Impact

Adds one test file and workflow entries only.
