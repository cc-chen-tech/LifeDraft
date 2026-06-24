## ADDED Requirements

### Requirement: Music Playlist Routes Enforce Game Ownership
Music playlist routes SHALL expose and mutate playlist state only for the authenticated owner of the underlying game.

#### Scenario: Unauthenticated caller reads a playlist
- **GIVEN** a game has a persisted playlist
- **WHEN** an unauthenticated caller requests `GET /api/music/playlist/{game_id}`
- **THEN** the API MUST reject the request
- **AND** the response MUST NOT include current song, queue, playback position, or volume.

#### Scenario: Authenticated user accesses another user's playlist
- **GIVEN** user B owns a game with a persisted playlist
- **WHEN** user A requests playlist read, update, sync, or advance routes for user B's `game_id`
- **THEN** each API call MUST return a not-found or forbidden response
- **AND** user B's playlist MUST remain unchanged.

### Requirement: Generated Music Enqueue Enforces Game Ownership
Generated story music routes SHALL enqueue tracks only for games owned by the authenticated caller.

#### Scenario: Authenticated user generates music for another user's game
- **GIVEN** user B owns a game
- **WHEN** user A requests `/api/music/generate` or `/api/music/generate-async` for user B's `game_id`
- **THEN** the API MUST reject the request before generating or enqueueing music
- **AND** no background generation task MAY be scheduled for user B's game.
