## ADDED Requirements

### Requirement: Maintained gate includes world breathing contracts
The maintained backend workflows SHALL execute `tests/test_narrative_world_breathing.py` without mocks, skips, environment mutation, external network access, or random input.

#### Scenario: Maintained backend workflow runs
- **WHEN** either maintained backend workflow executes
- **THEN** it MUST include the world breathing contract in the same ordered selection
