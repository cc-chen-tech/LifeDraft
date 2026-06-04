## ADDED Requirements

### Requirement: AI-generated music degrades to existing music without blocking gameplay
The system SHALL treat MiniMax generated music as a non-blocking supplement to existing recommendations and SHALL preserve gameplay and playback when generation is unavailable.

#### Scenario: MiniMax music generation is unavailable
- **GIVEN** story content has generated successfully
- **AND** MiniMax music generation is disabled, unconfigured, unavailable, or failed
- **WHEN** the music service refreshes recommendations
- **THEN** the UI MUST keep story choices and continuation controls usable
- **AND** the player MUST keep the current track or NetEase queue usable
- **AND** the UI MUST NOT show generated music as ready.

#### Scenario: Generated music URL must be browser-safe
- **GIVEN** MiniMax music generation returns a playable asset URL or downloaded generated asset
- **WHEN** the frontend receives the generated track
- **THEN** the system MUST expose an HTTPS-safe or same-origin URL to the browser
- **AND** the browser MUST NOT emit mixed-content audio warnings.

### Requirement: Generated music must not interrupt current playback
The system SHALL insert generated MiniMax tracks only into future playlist queue slots.

#### Scenario: Generated track insertion preserves current song
- **GIVEN** the music player has a current song and an existing queue
- **WHEN** a MiniMax generated track becomes ready
- **THEN** the current song MUST remain unchanged
- **AND** the generated track MUST be inserted into the future queue according to playlist queue policy.
