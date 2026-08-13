## ADDED Requirements

### Requirement: Maintained gate includes relationship event contracts
The maintained backend workflows SHALL execute `tests/test_relationship_events_contract.py` without mocks, skips, environment mutation, external network access, or random input.

#### Scenario: Maintained backend workflow runs
- **WHEN** either maintained backend workflow executes
- **THEN** it MUST include the relationship event contract in the same ordered selection
