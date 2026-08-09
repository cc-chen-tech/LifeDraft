## ADDED Requirements

### Requirement: Maintained gate includes round system-mixin contracts
The maintained backend workflows SHALL execute `tests/test_system_mixin_contract.py` without mocks, skips, environment mutation, external network access, or random input.

#### Scenario: Maintained backend workflow runs
- **WHEN** either maintained backend workflow executes
- **THEN** it MUST include the round system-mixin contract in the same ordered selection
