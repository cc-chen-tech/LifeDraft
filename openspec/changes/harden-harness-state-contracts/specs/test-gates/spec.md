## ADDED Requirements

### Requirement: Maintained state contracts are symmetric
The maintained backend coverage and backend test workflows SHALL list verified harness-state contracts in the same order.

#### Scenario: Workflow selections are compared
- **WHEN** both maintained workflow lists are extracted
- **THEN** their ordered test-file paths MUST be identical
