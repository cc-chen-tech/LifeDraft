## ADDED Requirements

### Requirement: Maintained gate includes game-loop load recovery contracts
The maintained backend workflows SHALL execute `tests/test_game_loop_load_recovery_contracts.py` without mocks, skips, environment mutation, external network access, or random input.

#### Scenario: Maintained backend workflow runs
- **WHEN** either maintained backend workflow executes
- **THEN** it MUST include the game-loop load recovery contract in the same ordered selection
