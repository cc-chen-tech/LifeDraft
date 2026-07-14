## ADDED Requirements

### Requirement: Maintained character-creation contracts are symmetric
The maintained backend coverage workflow and maintained backend test workflow SHALL list the twice-verified character-creation contract suite in the same order.

#### Scenario: Workflow selection is compared
- **WHEN** maintained backend selections are extracted from both workflows
- **THEN** their ordered test-file lists MUST be identical
