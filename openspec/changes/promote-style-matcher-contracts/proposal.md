## Why

Style selection is a deterministic narrative boundary, yet its verified contract suite is absent from maintained coverage. Promotion catches incorrect default-style fallback before it reaches generated stories.

## What Changes

- Add the existing style-matching contract suite to both maintained workflows.

## Capabilities

### New Capabilities
- `style-matcher-maintained-gate`: Require deterministic style matching contracts in the maintained backend suite.

### Modified Capabilities

- None.

## Impact

Only maintained workflow test lists change.
