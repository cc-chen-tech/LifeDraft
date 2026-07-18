## ADDED Requirements

### Requirement: Cached opening-story SSE contract coverage
The maintained backend suite SHALL verify that a fresh cached opening story is replayed as status, story, and complete SSE frames without regeneration.

#### Scenario: Replay a cached opening story
- **WHEN** a player has a fresh cached opening-story result
- **THEN** the endpoint emits cached status, the exact story text, and a complete frame with the same text

### Requirement: Duplicate opening-story request contract coverage
The maintained backend suite SHALL verify that a fresh in-flight opening-story request rejects a duplicate before provider generation.

#### Scenario: Reject a duplicate request
- **WHEN** an opening story is marked generating for less than the stale timeout
- **THEN** the endpoint raises a 409 HTTP error

### Requirement: Opening-story truncation boundary coverage
The maintained backend suite SHALL verify explicit length and trivial text truncation decisions.

#### Scenario: Evaluate known truncation states
- **WHEN** a response is empty, too short, or marked with length finish reason
- **THEN** the helper returns the documented boolean decision
