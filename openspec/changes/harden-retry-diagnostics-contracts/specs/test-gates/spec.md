## ADDED Requirements

### Requirement: Retry diagnostic selection is symmetric
The maintained coverage and backend-test workflows SHALL list verified retry and diagnostic suites in the same order.

#### Scenario: Workflow lists are compared
- **WHEN** selections are extracted
- **THEN** their ordered test paths MUST be identical
