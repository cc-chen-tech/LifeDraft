## ADDED Requirements

### Requirement: Maintained gate includes session scene-storage contracts
The maintained backend workflows SHALL execute `tests/test_session_service_scene_storage_contracts.py` without mocks, skips, environment mutation, external network access, or random input.

#### Scenario: Maintained backend workflow runs
- **WHEN** either maintained backend workflow executes
- **THEN** it MUST include the session scene-storage contract in the same ordered selection
