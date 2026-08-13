## ADDED Requirements

### Requirement: Maintained backend gate covers image executor lifecycle
The maintained backend workflows SHALL include the deterministic image thread-pool lifecycle contract without mocked executors, skip directives, provider access, or environment mutation.

#### Scenario: Maintained workflows execute the image executor contract
- **WHEN** either maintained backend workflow runs
- **THEN** it MUST execute `tests/test_image_thread_pool_contract.py` in the same ordered test selection
