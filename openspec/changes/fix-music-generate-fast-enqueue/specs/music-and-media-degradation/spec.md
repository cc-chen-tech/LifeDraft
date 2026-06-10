## MODIFIED Requirements

### Requirement: AI-generated music degrades to existing music without blocking gameplay
The system SHALL treat MiniMax generated music as a non-blocking supplement to existing recommendations and SHALL preserve gameplay and playback when generation is unavailable or still pending.

#### Scenario: Music generation is enqueued without blocking the API request by default
- **GIVEN** MiniMax music generation is enabled with real provider credentials
- **WHEN** the client requests `/api/music/generate` after a story is complete
- **THEN** the API SHALL return HTTP 202 with `status: queued`
- **AND** the route SHALL NOT call the blocking ready-track generation path before returning
- **AND** generated music SHALL still be inserted into the future playlist queue by background generation when it becomes ready.

#### Scenario: Story-complete playback uses the primary non-blocking music generation route
- **GIVEN** a story recommendation includes a `music_brief`
- **WHEN** the frontend starts AI music generation for the completed story
- **THEN** the frontend SHALL enqueue generation through `/api/music/generate`
- **AND** the frontend SHALL NOT depend on `/api/music/generate-async` for the normal story-complete playback path
- **AND** the current NetEase baseline song SHALL remain current while generated music is inserted into the future queue when ready.

#### Scenario: Local deterministic generated music remains explicitly synchronously verifiable
- **GIVEN** MiniMax local-audio mode is enabled for deterministic tests
- **WHEN** the client requests `/api/music/generate?sync=true`
- **THEN** the API SHALL return HTTP 200 with a ready generated track
- **AND** the ready generated track SHALL use the future playlist insertion policy.
