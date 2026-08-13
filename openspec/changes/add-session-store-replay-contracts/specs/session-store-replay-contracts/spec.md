## ADDED Requirements

### Requirement: Reconnect and options cache state remains scoped to the current session
The maintained backend suite SHALL verify replay-tail ordering, story-sensitive option cache invalidation, session owner isolation, and expiry cleanup.

#### Scenario: Resuming a session after state changes
- **WHEN** chunks, options, and sessions are stored for multiple game owners
- **THEN** replay and cache lookup return only valid current-session state and expired records are removed
