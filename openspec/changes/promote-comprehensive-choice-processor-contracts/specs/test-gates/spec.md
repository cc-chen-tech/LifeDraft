## ADDED Requirements

### Requirement: Maintained gate includes comprehensive choice contracts
The maintained backend workflows SHALL execute `tests/test_choice_processor_contract.py` without framework mocks, skips, environment mutation, external network access, or random input.

#### Scenario: Maintained backend workflow runs
- **WHEN** either maintained backend workflow executes
- **THEN** it MUST include the comprehensive choice processor contract in the same ordered selection
