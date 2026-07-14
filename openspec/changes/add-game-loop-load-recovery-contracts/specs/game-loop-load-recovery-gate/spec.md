## ADDED Requirements

### Requirement: Maintained gate validates saved current-event recovery
The maintained backend selection SHALL validate GameLoop restoration of valid saved events, clearing of stale events, and recoverable partial event preservation.

#### Scenario: Saved event is already in history
- **WHEN** a saved current event matches an already processed week and round
- **THEN** the maintained contract MUST require the stale current event to be cleared
