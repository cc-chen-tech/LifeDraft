## ADDED Requirements

### Requirement: Maintained character-arc contract coverage
The maintained backend workflows SHALL execute
`tests/test_narrative_character_arc.py` in identical ordered test selections.

#### Scenario: Character-arc regression protection
- **WHEN** a maintained backend workflow runs
- **THEN** it validates deterministic character-arc creation, progression,
  style, constraint, and degradation contracts without an external provider.

#### Scenario: Selection parity
- **WHEN** the maintained coverage and backend-test selections are parsed
- **THEN** their ordered lists contain the same character-arc suite entry.

### Requirement: Promotion verification
The character-arc promotion SHALL be verified by direct execution, a
maintained-dependency scan, selection parity comparison, and a complete
maintained coverage run.

#### Scenario: Current threshold is preserved
- **WHEN** the promoted selection executes in CI-like settings
- **THEN** every selected test passes and the configured coverage threshold is
  reached.
