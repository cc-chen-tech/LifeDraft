## ADDED Requirements

### Requirement: SSE terminal states remain replayable and safe
The SSE helpers SHALL emit stable completion and failure frames, return a terminal snapshot for completed or failed operations, and time out a still-running operation without cancelling it.

#### Scenario: Terminal operation subscriber
- **WHEN** an event operation completes or fails before a subscriber waits
- **THEN** the subscriber MUST receive the matching terminal snapshot and SSE frame

#### Scenario: Running operation timeout
- **WHEN** an operation remains running beyond a subscriber timeout
- **THEN** waiting MUST raise an async timeout without mutating the operation
