## Why

Summary responses populate long-lived narrative and world state, but the maintained backend gate does not protect their deterministic response normalization, defaulting, or bonus-effect filtering.

## What Changes

- Add local SummaryGenerator recovery contracts to both maintained backend workflows.

## Capabilities

### New Capabilities

- `summary-generator-recovery-maintained-gate`: Require maintained contracts for structured summary response normalization and safe defaults.

### Modified Capabilities

- None.

## Impact

Adds one test file and workflow entries only.
