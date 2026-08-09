## ADDED Requirements

### Requirement: Maintained pure SSE protocol coverage
The maintained backend workflows SHALL execute deterministic contracts for SSE
event framing, retry cache behavior, generation identity, and terminal replay.

#### Scenario: Framed event is reconnect-safe
- **WHEN** an SSE event is created with an event identifier
- **THEN** it contains the identifier, event type, JSON data line, and a blank
  line terminator.

#### Scenario: Retry cache is cleared only for retry phase
- **WHEN** a status payload reports a retry phase
- **THEN** the session cache is cleared exactly once.

#### Scenario: Completed reconnect emits terminal event
- **WHEN** a completed event is replayed to a reconnecting client
- **THEN** the stream emits resuming status followed by the complete payload.
