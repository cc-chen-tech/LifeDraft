## ADDED Requirements

### Requirement: State authority contracts are maintained-gate coverage
The maintained backend workflows SHALL execute deterministic contracts for the continuity ledger, wealth ledger, wealth consumers, and persisted player-state submodules.

#### Scenario: State authority regression
- **WHEN** a change breaks a continuity, wealth, finalization, or player-state persistence invariant
- **THEN** both maintained backend workflows fail before release.

### Requirement: Maintained workflow lists stay ordered equivalents
The coverage and backend-test workflows SHALL list the promoted state authority suites in the same order.

#### Scenario: Workflow parity check
- **WHEN** the maintained test lists are extracted from both workflows
- **THEN** the ordered lists are identical.

### Requirement: Promoted tests remain provider-free
The promoted suites SHALL run using only deterministic in-process state and local test-database behavior, without mocks, browser execution, or external providers.

#### Scenario: Isolated maintained execution
- **WHEN** the promoted suites run with CI test environment variables
- **THEN** all selected tests complete without network or provider credentials.
