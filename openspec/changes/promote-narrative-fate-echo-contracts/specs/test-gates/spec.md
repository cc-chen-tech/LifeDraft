## ADDED Requirements

### Requirement: Maintained gate includes fate echo contracts
The maintained backend workflows SHALL execute `tests/test_narrative_fate_echo.py` without mocks, skips, environment mutation, external network access, or random input.

#### Scenario: Maintained backend workflow runs
- **WHEN** either maintained backend workflow executes
- **THEN** it MUST include the narrative fate echo contract in the same ordered selection
