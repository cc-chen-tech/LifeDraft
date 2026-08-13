## ADDED Requirements

### Requirement: Completed SSE operations replay only unseen chunks
The maintained test suite SHALL verify that reconnecting to a completed round
operation emits the resuming state, story chunks newer than the supplied event
cursor, and the terminal event payload.

#### Scenario: Reconnect after completion
- **WHEN** a subscriber reconnects with the ID of an already received story
  chunk
- **THEN** the SSE stream MUST not repeat that chunk and MUST emit the later
  chunk with its ID before the complete payload
