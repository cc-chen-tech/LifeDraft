## ADDED Requirements

### Requirement: Pipeline gate selection is symmetric
The maintained coverage and backend-test workflows SHALL list the validation pipeline contract suite in the same order.

#### Scenario: Workflow lists are compared
- **WHEN** maintained selections are extracted
- **THEN** their ordered test paths MUST be identical
