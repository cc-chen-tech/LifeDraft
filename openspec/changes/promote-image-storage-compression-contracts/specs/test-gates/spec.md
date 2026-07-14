## ADDED Requirements

### Requirement: Maintained gate includes image storage compression coverage
The maintained backend workflows SHALL run `tests/test_image_compression_db.py` without mocks, skips, environment mutation, external network access, or random input.

#### Scenario: Maintained backend workflow runs
- **WHEN** either maintained backend workflow executes
- **THEN** it MUST include the image storage compression contract in the same ordered selection
