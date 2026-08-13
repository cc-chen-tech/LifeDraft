## Why

The maintained backend suite omits deterministic validation and recovery tests that protect generated story correctness. These verified suites cover content constraints, fast-generation budgets, and truncation recovery without calling external AI services.

## What Changes

- Add existing quick-validator, harness-logic, era-validator, constraint-level, truncation-recovery, and generation-budget suites to both maintained workflows.
- Preserve provider-free execution and ordered workflow parity.

## Capabilities

### New Capabilities
- `ai-validation-recovery-maintained-gate`: Require deterministic AI validation and truncation recovery contracts in the maintained backend suite.

### Modified Capabilities

- None.

## Impact

Only maintained test lists change; production code and existing tests remain unchanged.
