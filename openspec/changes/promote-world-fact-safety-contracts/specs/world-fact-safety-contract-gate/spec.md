## ADDED Requirements

### Requirement: Maintained world-fact safety coverage
The maintained backend workflows SHALL execute
`tests/test_world_fact_safety_contract_no_mock.py` in identical ordered
selections.

#### Scenario: Precise claims are qualified
- **WHEN** generated world fields make precise real-sounding claims
- **THEN** the returned fields visibly identify those claims as fictional
  setting assumptions.

#### Scenario: Qualitative fiction remains unchanged
- **WHEN** generated world fields are qualitative rather than precise claims
- **THEN** qualification leaves the fields unchanged.

### Requirement: Stable maintained verification
The promotion SHALL pass the complete maintained test selection at the current
51% coverage minimum.

#### Scenario: Gate succeeds
- **WHEN** the promoted maintained coverage workflow runs with CI-like settings
- **THEN** all selected tests pass and coverage meets the 51% threshold.
