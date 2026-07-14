## ADDED Requirements

### Requirement: Preflight gate selection is symmetric
The maintained coverage and backend-test workflows SHALL list verified preflight contract suites in the same order.

#### Scenario: Workflow lists are compared
- **WHEN** maintained selections are extracted
- **THEN** their ordered test paths MUST be identical
