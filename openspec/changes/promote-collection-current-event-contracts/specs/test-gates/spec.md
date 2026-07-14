## ADDED Requirements

### Requirement: Maintained gate covers current-event collection context
The maintained backend workflows SHALL run `tests/test_collection_recognition_current_event.py` without mocks, skips, environment mutation, external network access, or random input.

#### Scenario: Maintained backend workflow runs
- **WHEN** either maintained backend workflow executes
- **THEN** it MUST include the current-event collection-recognition contract in the same ordered selection
