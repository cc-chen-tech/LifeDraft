## ADDED Requirements

### Requirement: Maintained NPC contracts are symmetric
The maintained backend coverage workflow and maintained backend test workflow SHALL list twice-verified NPC attribute contracts in the same order.

#### Scenario: Workflow selection is compared
- **WHEN** maintained backend selections are extracted
- **THEN** their ordered test-file lists MUST be identical
