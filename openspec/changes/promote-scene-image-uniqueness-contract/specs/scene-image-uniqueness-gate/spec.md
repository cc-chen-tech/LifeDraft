## ADDED Requirements

### Requirement: Maintained gate verifies the SceneImage persistence key
The maintained backend test selection SHALL run the deterministic SceneImage unique-index contract in both coverage and backend-test workflows.

#### Scenario: Composite key schema regresses
- **WHEN** the SceneImage composite index is missing, non-unique, has a missing key column, or changes column order
- **THEN** the maintained backend gate MUST fail
