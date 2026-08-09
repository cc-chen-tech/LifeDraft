## ADDED Requirements

### Requirement: Maintained gate includes gameplay event protocol contracts
The maintained backend workflows SHALL execute `tests/test_gameplay_event_protocol_contracts.py` without mocks, skips, environment mutation, external network access, or random input.

#### Scenario: Maintained backend workflow runs
- **WHEN** either maintained backend workflow executes
- **THEN** it MUST include the gameplay event protocol contract in the same ordered selection
