## ADDED Requirements

### Requirement: Maintained gates cover fallback gameplay contracts
The maintained backend test and coverage workflows SHALL include deterministic fallback-event contracts for localized recovery events, round labels, scheduled-event text, options, and effects.

#### Scenario: Generation fallback regression
- **WHEN** a fallback event loses its user-visible structure or actionable options
- **THEN** the maintained backend gate MUST fail before release-only validation

### Requirement: Maintained gates cover scheduled-event state contracts
The maintained backend test and coverage workflows SHALL include deterministic contracts for scheduled-event time parsing, matching, overdue detection, merge behavior, lifecycle transitions, cleanup, and serialization.

#### Scenario: Scheduling state regression
- **WHEN** a change breaks a scheduled event's timing or lifecycle semantics
- **THEN** the maintained backend gate MUST fail before release-only validation

### Requirement: Maintained workflow selections remain equivalent
The maintained backend test workflow and maintained coverage workflow SHALL select the fallback and scheduling contract suites exactly once and in the same order.

#### Scenario: Workflow selection review
- **WHEN** fallback and scheduling suites are added to a maintained workflow
- **THEN** both workflows MUST contain the same ordered paths
