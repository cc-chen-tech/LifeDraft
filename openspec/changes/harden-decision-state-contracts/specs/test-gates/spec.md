## ADDED Requirements

### Requirement: Maintained decision contracts are symmetric
The maintained backend coverage workflow and maintained backend test workflow SHALL list twice-verified decision state contracts in the same order.

#### Scenario: Workflow selection is compared
- **WHEN** maintained backend selections are extracted
- **THEN** their ordered test-file lists MUST be identical
