## Why

Dynamic facts and scheduled commitments originate in model responses, but their deterministic parsing, normalization, and lifecycle transitions are not protected by the maintained backend gate.

## What Changes

- Add provider-free StoryAnalyzer parsing contracts to both maintained backend workflows.

## Capabilities

### New Capabilities

- `story-analyzer-parsing-maintained-gate`: Require maintained contracts for dynamic-fact and scheduled-commitment response parsing.

### Modified Capabilities

- None.

## Impact

Adds one test file and workflow entries only.
