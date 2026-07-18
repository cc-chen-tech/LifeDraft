## ADDED Requirements

### Requirement: Choice SSE success contract coverage
The maintained backend suite SHALL verify that a successful choice exposes preparation, status, story, and complete frames through the real session cache.

#### Scenario: Complete a normal choice
- **WHEN** a local choice loop emits one status and one story chunk then returns a result
- **THEN** the stream exposes those frames and a terminal complete payload

### Requirement: Choice SSE replay and error contract coverage
The maintained backend suite SHALL verify cached replay and terminal data-error cleanup.

#### Scenario: Reconnect before a choice completes
- **WHEN** a session contains a cached chunk and the client supplies an earlier cursor
- **THEN** the stream replays the cached chunk before new output

#### Scenario: Choice input fails validation
- **WHEN** the local choice loop raises a data error
- **THEN** the stream emits an error frame and clears the session SSE cache
