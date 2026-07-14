## ADDED Requirements

### Requirement: Maintained content contracts are symmetric
The maintained coverage and backend-test workflows SHALL list verified harness content contract suites in the same order.

#### Scenario: Workflow selections are compared
- **WHEN** maintained backend selection paths are extracted from both workflows
- **THEN** their ordered lists MUST be identical
