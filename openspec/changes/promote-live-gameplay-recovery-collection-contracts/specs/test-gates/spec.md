## ADDED Requirements

### Requirement: Maintained backend gate includes live recovery regressions
The maintained backend workflows SHALL include the live gameplay recovery collection contract without framework mocks, skip directives, environment mutation, external provider access, or non-deterministic input.

#### Scenario: Maintained workflows execute recovery collection contracts
- **WHEN** either maintained backend workflow runs
- **THEN** it MUST execute `tests/test_live_gameplay_recovery_collection_contract.py` in the same ordered test selection
