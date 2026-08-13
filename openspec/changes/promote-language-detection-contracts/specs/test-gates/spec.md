## ADDED Requirements

### Requirement: Maintained gate includes language detection contracts
The maintained backend workflows SHALL execute `tests/test_language_contract.py` without mocks, skips, environment mutation, external network access, or random input.

#### Scenario: Maintained backend workflow runs
- **WHEN** either maintained backend workflow executes
- **THEN** it MUST include the language detection contract in the same ordered selection
