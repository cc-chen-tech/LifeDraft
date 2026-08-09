## ADDED Requirements

### Requirement: Maintained gate includes image compressor contracts
The maintained backend workflows SHALL execute `tests/test_image_compressor_db.py` without mocks, skips, environment mutation, external network access, or random input.

#### Scenario: Maintained backend workflow runs
- **WHEN** either maintained backend workflow executes
- **THEN** it MUST include the image compressor contract in the same ordered selection
