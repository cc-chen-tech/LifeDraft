## ADDED Requirements

### Requirement: Maintained persisted narrative-style restoration coverage
The maintained backend workflows SHALL execute
`tests/test_narrative_style_restore_contract.py` in identical ordered
selections.

#### Scenario: Persisted field compatibility
- **WHEN** a maintained backend workflow runs
- **THEN** it validates restoration of present, missing, null, and empty
  narrative-style field values from a saved game-state dictionary.

#### Scenario: Workflow list parity
- **WHEN** maintained coverage and backend-test workflow selections are parsed
- **THEN** both ordered lists contain the same style-restore suite entry.

### Requirement: Verified threshold advance
The maintained threshold SHALL advance to 51% only after the complete promoted
selection passes with `--cov-fail-under=51`.

#### Scenario: 51 percent gate passes
- **WHEN** the complete maintained suite reaches at least 51% coverage
- **THEN** the coverage workflow enforces a 51% minimum.

#### Scenario: 51 percent gate does not pass
- **WHEN** the complete maintained suite is below 51% coverage
- **THEN** the coverage workflow retains its prior verified minimum.
