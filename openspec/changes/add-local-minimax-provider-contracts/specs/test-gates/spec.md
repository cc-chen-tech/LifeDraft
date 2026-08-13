## ADDED Requirements

### Requirement: Maintained backend gate covers local image-provider transport
The maintained backend workflows SHALL include loopback-only image provider contracts without mocks, skip directives, environment mutation, external network access, or provider credentials.

#### Scenario: Maintained workflows execute local provider contracts
- **WHEN** either maintained backend workflow runs
- **THEN** it MUST execute `tests/test_local_minimax_provider_contracts.py` in the same ordered test selection
