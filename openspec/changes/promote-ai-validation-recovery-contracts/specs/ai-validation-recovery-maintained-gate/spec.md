## ADDED Requirements

### Requirement: AI validation and recovery contracts are maintained
The maintained backend workflows SHALL execute deterministic content validation, generation-budget, and truncation-recovery contracts.

#### Scenario: Validation regression
- **WHEN** a narrative constraint or truncation-recovery invariant regresses
- **THEN** both maintained workflows fail before release.

### Requirement: Validation workflow parity is preserved
The maintained coverage and backend-test workflows SHALL list promoted validation suites in identical order.

#### Scenario: Ordered parity
- **WHEN** test paths are extracted from both workflows
- **THEN** the ordered lists are identical.
