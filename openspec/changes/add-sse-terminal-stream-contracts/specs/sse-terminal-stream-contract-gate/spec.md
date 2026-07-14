## ADDED Requirements

### Requirement: Terminal event generation is replayable
The maintained backend gate SHALL verify that completed durable operations emit
the expected SSE status and terminal payload without starting a new worker.

#### Scenario: Completed operation replays chunks then result
- **WHEN** a subscriber reconnects to a completed operation
- **THEN** it SHALL receive resuming, terminal phase, unseen chunks, and complete
  result events

### Requirement: Generation conflict and resume view remain observable
The maintained backend gate SHALL verify conflicting operation identities and
the player resume view used while a worker is active.

#### Scenario: Different active operation conflicts
- **WHEN** a different round is already running
- **THEN** the stream SHALL return an error rather than start another worker
