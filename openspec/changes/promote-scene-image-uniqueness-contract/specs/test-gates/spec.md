## ADDED Requirements

### Requirement: Maintained backend gate covers SceneImage key uniqueness
The maintained backend workflows SHALL include the deterministic SceneImage composite unique-index contract without mocks, skip directives, provider access, or environment mutation.

#### Scenario: Maintained workflows execute the SceneImage constraint contract
- **WHEN** either maintained backend workflow runs
- **THEN** it MUST execute `tests/test_scene_image_constraint_contract.py` in the same ordered test selection
