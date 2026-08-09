## ADDED Requirements

### Requirement: Maintained gates cover scheduled-event game-state flow
The maintained backend test and coverage workflows SHALL include deterministic scheduled-event tests that verify Commitment conversion and PlayerState pending, triggered, and overdue event behavior.

#### Scenario: Commitment becomes a scheduled event
- **WHEN** a commitment carries scheduling information
- **THEN** the maintained backend gate MUST fail if conversion no longer preserves the intended event timing and context

#### Scenario: Player state tracks scheduled events
- **WHEN** player state adds, selects, triggers, or finds overdue scheduled events
- **THEN** the maintained backend gate MUST fail if the lifecycle state becomes inconsistent
