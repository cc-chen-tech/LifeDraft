## ADDED Requirements

### Requirement: Music playback advances through the persistent queue

When a story music track ends or the player requests the next track, playback SHALL advance through the persistent playlist queue before falling back to the original recommendation list.

#### Scenario: Generated music arrives while the current song is playing

- **GIVEN** a NetEase baseline song is currently playing
- **AND** a MiniMax-generated track has been inserted at the head of the future queue
- **WHEN** the current song ends
- **THEN** the player MUST call the playlist advance path
- **AND** the generated track MUST become the next current song
- **AND** the player MUST NOT skip it by using a stale recommendation list captured before generation completed
