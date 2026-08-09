## ADDED Requirements

### Requirement: Reconnected round-event subscribers replay only unseen frames
The round-event SSE stream SHALL emit only story chunks with IDs greater than the
subscriber's last event ID, followed by the durable terminal result.

#### Scenario: Completed operation is resumed after one story chunk was received
- **GIVEN** a completed operation with two numbered story chunks
- **WHEN** a subscriber reconnects with the first chunk's event ID
- **THEN** the stream emits only the second story chunk
- **AND** it terminates with the completed event payload.

### Requirement: Terminal failures are explicit SSE errors
The round-event SSE stream SHALL finish a failed operation with an error frame
and SHALL NOT emit a complete frame.

#### Scenario: Durable worker fails before a subscriber connects
- **GIVEN** a failed operation with a worker error message
- **WHEN** a subscriber opens the stream
- **THEN** the stream emits that error message in an error frame
- **AND** no complete frame is emitted.

### Requirement: Generation conflicts fail fast on the SSE protocol
The round-event SSE stream SHALL expose an operation ownership conflict as one
error frame instead of waiting for a worker that cannot start.

#### Scenario: Session rejects a conflicting generation key
- **GIVEN** operation acquisition raises an event-generation conflict
- **WHEN** a subscriber opens the stream
- **THEN** the stream emits the conflict message as an error frame and ends.
