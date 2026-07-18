## ADDED Requirements

### Requirement: Maintained backend gates have one manifest
The system SHALL define the maintained backend test selection in one
repository-owned runner and both backend CI workflows MUST invoke that runner.

#### Scenario: Normal backend gate
- **WHEN** the backend test workflow runs
- **THEN** it executes the runner in normal test mode

#### Scenario: Backend coverage gate
- **WHEN** the coverage workflow runs
- **THEN** it executes the same runner in coverage mode

### Requirement: OpenAPI preflight is hermetic
The preflight check SHALL generate OpenAPI comparison artifacts under the
active test run directory and MUST compare them to tracked artifacts without
writing tracked files.

#### Scenario: Generated artifacts match
- **WHEN** generated schema and declarations equal the tracked artifacts
- **THEN** preflight succeeds and the worktree remains unchanged

#### Scenario: Generated artifacts drift
- **WHEN** either generated artifact differs from its tracked counterpart
- **THEN** preflight fails with a drift signal and the worktree remains unchanged
