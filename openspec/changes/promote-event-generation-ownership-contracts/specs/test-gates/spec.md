## ADDED Requirements

### Requirement: Maintained gates cover event-generation ownership contracts
The maintained backend test and coverage workflows SHALL include deterministic contracts for event-generation operation ownership, replay, completion reuse, failure replacement, and SSE error framing.

#### Scenario: Concurrent producer claim regression
- **WHEN** a change allows multiple producers for one event-generation operation key
- **THEN** the maintained backend gate MUST fail before release-only validation

#### Scenario: Replay or terminal-state regression
- **WHEN** a change breaks replay after a cursor, completed-operation reuse, or replacement after a failure
- **THEN** the maintained backend gate MUST fail before release-only validation

### Requirement: Maintained workflow selections remain equivalent
The maintained backend test workflow and maintained coverage workflow SHALL select the event-generation ownership contract suite exactly once and in the same order.

#### Scenario: Workflow selection review
- **WHEN** the event-generation ownership suite is added to a maintained workflow
- **THEN** both workflows MUST contain the same path-list entry
