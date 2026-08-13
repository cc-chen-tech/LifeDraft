## ADDED Requirements

### Requirement: Maintained ConflictTower contract coverage
The maintained backend workflows SHALL execute
`tests/test_narrative_conflict_tower.py` as part of their identical ordered test
selection.

#### Scenario: Deterministic maintained execution
- **WHEN** a maintained backend workflow runs
- **THEN** it executes the ConflictTower suite without external-provider or
  mock-framework dependencies.

#### Scenario: Workflow selection parity
- **WHEN** the coverage and backend-test workflow selections are parsed
- **THEN** their ordered test-file lists include the same ConflictTower entry
  and remain identical.

### Requirement: Promotion verification
The promotion SHALL be verified by running the direct suite, scanning it for
forbidden maintained-gate dependencies, and running the complete maintained
coverage command at the configured threshold.

#### Scenario: Stable gate result
- **WHEN** the updated maintained test selection is run with CI-like settings
- **THEN** all selected tests pass and the configured coverage threshold is met.
