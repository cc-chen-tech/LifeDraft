## ADDED Requirements

### Requirement: Reconnect replay retains correctly numbered cached tail
The maintained backend suite SHALL verify that a bounded SSE cache replays the
remaining tail with its original event IDs and is empty after reset.

#### Scenario: Cached replay after bounded trimming
- **WHEN** a session caches more SSE chunks than its configured capacity
- **THEN** replay after an earlier event ID returns only retained chunks with
  their original sequential event IDs

#### Scenario: Cache reset after generation lifecycle
- **WHEN** a session clears its SSE replay cache
- **THEN** no chunk is available for a reconnect replay

### Requirement: Options cache is scoped to its story lifecycle
The maintained backend suite SHALL verify that cached options are returned only
for the matching story content and that the prefetch lifecycle resets cleanly.

#### Scenario: Story content changes
- **WHEN** cached options are read with different story content for the same
  week and round
- **THEN** the cache lookup returns no options

#### Scenario: Prefetch completion and clear
- **WHEN** options prefetch finishes and the options cache is cleared
- **THEN** the prefetch flag is false and no cached options remain

### Requirement: Session entries remain owner-isolated and expire
The maintained backend suite SHALL verify that one user's cached session cannot
be read as another user's session and that expired sessions are removed.

#### Scenario: Same game ID for different users
- **WHEN** two users store sessions for the same game ID
- **THEN** each user reads only its own session and cached data survives an
  update of that user's session

#### Scenario: Expired owner session cleanup
- **WHEN** a user's session is past the configured timeout during cleanup
- **THEN** it is absent while an unexpired session for another user remains
