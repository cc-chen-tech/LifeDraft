## Why

The validation pipeline is the deterministic aggregation boundary for generated-story constraints, but its stable public contract suite is not in the maintained backend gate. Regressions in priority routing, scoring, profile filtering, and exception degradation can therefore bypass fast feedback.

## What Changes

- Promote the existing no-double validation pipeline contract suite into both maintained backend workflows.
- Measure the expanded selection twice and ratchet the coverage floor only from repeatable evidence.

## Capabilities

### New Capabilities
- `validation-pipeline-maintained-contracts`: Stable maintained coverage for validation-pipeline public behavior.

### Modified Capabilities
- `test-gates`: Maintained backend workflow selections include the validation pipeline suite in identical order.

## Impact

- Affects workflow test lists, coverage threshold when supported, and OpenSpec artifacts only.
