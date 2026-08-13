## ADDED Requirements

### Requirement: Maintained narrative state contracts are symmetric
The maintained backend coverage workflow and maintained backend test workflow SHALL list the twice-verified narrative state contract suite in the same order.

#### Scenario: Workflow selection is compared
- **WHEN** the maintained backend selections are extracted from both workflows
- **THEN** their ordered test-file lists MUST be identical

#### Scenario: Narrative contracts execute in a maintained gate
- **WHEN** either maintained backend workflow runs
- **THEN** narrative state contracts MUST complete without mocks, a provider,
  database, random patch, or timing dependency
