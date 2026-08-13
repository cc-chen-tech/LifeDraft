## ADDED Requirements

### Requirement: Maintained scene and summary contracts are symmetric
The maintained backend coverage workflow and maintained backend test workflow SHALL list the twice-verified scene and historical-summary contract suites in the same order.

#### Scenario: Workflow selection is compared
- **WHEN** the maintained test selections are extracted from both workflows
- **THEN** their ordered test-file lists MUST be identical

#### Scenario: A maintained contract is rerun
- **WHEN** either maintained backend workflow runs the scene and summary
  contract suites
- **THEN** the suites MUST complete without a provider, network call, mock, or
  timing dependency
