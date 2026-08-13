## ADDED Requirements

### Requirement: Choice SSE success coverage
The maintained backend suite SHALL verify successful choice SSE frames through
the real session replay cache.

#### Scenario: Complete a normal choice
- **WHEN** a local choice loop emits status and story data then returns a result
- **THEN** the stream emits preparation, status, story, and complete frames

### Requirement: Choice SSE replay and terminal error coverage
The maintained backend suite SHALL verify replay ordering and cache cleanup for
terminal data errors.

#### Scenario: Reconnect to cached choice output
- **WHEN** a client supplies an earlier cursor for a session with cached data
- **THEN** the cached story frame is emitted before new choice output

#### Scenario: Invalid choice data
- **WHEN** a local choice loop raises a data validation error
- **THEN** the stream emits an error frame and clears its replay cache
