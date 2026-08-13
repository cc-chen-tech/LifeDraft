## ADDED Requirements

### Requirement: Maintained gates cover periodic summary contracts
The maintained backend test and coverage workflows SHALL include deterministic monthly and yearly summary contract suites that verify summary record shape, player-state deltas, prompt context, and provider-failure fallback behavior.

#### Scenario: Monthly summary contract regression
- **WHEN** a change breaks monthly summary state deltas, generated prompt context, result fields, or its provider-error fallback
- **THEN** the maintained backend gate MUST fail before release-only validation

#### Scenario: Yearly summary contract regression
- **WHEN** a change breaks yearly summary state deltas, monthly highlight context, result fields, or its provider-error fallback
- **THEN** the maintained backend gate MUST fail before release-only validation

### Requirement: Maintained workflow selections remain equivalent
The maintained backend test workflow and maintained coverage workflow SHALL select the same periodic summary contract files in the same order.

#### Scenario: Workflow selection review
- **WHEN** the periodic summary suites are added to a maintained workflow
- **THEN** both workflows MUST contain the monthly suite followed by the yearly suite exactly once
