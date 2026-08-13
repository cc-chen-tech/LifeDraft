## ADDED Requirements

### Requirement: Rewritten SSE story state survives real persistence
The maintained backend suite SHALL verify with real SQLite persistence that a
rewritten current event remains authoritative after state reload while retaining
its non-text metadata.

#### Scenario: Rewrite updates a displayed current event
- **WHEN** a rewrite completes for a current event with options and display metadata
- **THEN** the reloaded state MUST contain the rewritten text in all displayed
  current-event text fields and retain the event metadata.

### Requirement: Generation recovery view survives real persistence
The maintained backend suite SHALL verify that a generating or failed SSE phase
is saved as a recoverable resume view with the active round coordinates.

#### Scenario: Generation becomes recoverable
- **WHEN** the durable event generation helper records a non-options phase
- **THEN** the reloaded state MUST expose that phase, its error when present,
  and the completed week and round.

### Requirement: Maintained workflows run SSE persistence contracts
Both maintained backend workflow lists SHALL include the SSE rewrite and resume
database contract path in matching order.

#### Scenario: Workflow parity
- **WHEN** the maintained workflow test lists are compared
- **THEN** the SSE persistence contract path SHALL occur in both lists at the
  same position.
