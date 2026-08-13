## Why

Narrative continuity depends on overdue storyline escalation and habit lifecycle transitions, while their current coverage is limited to legacy mock-bearing modules. These deterministic PlayerState transitions need maintained regression protection.

## What Changes

- Add provider-free tests for urgent and ordinary overdue storyline thresholds.
- Add habit weakening, removal, replacement, and normalization coverage.
- Include the new module in both maintained backend workflow lists.

## Capabilities

### New Capabilities
- `narrative-maintenance-contracts`: Maintained coverage for NarrativeManager overdue-storyline and habit lifecycle transitions.

### Modified Capabilities

- None.

## Impact

- Tests and paired CI workflow lists only; no production behavior changes.
