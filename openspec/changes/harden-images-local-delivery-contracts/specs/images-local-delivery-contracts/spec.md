## ADDED Requirements

### Requirement: Local image delivery contract coverage
The maintained backend suite SHALL verify that a stored local image is delivered as its original bytes with a content type and cache headers derived from its filename.

#### Scenario: Deliver a stored WebP image
- **WHEN** an owned local WebP file is requested through the image file route
- **THEN** the response contains the stored bytes, `image/webp` media type, and one-hour public cache metadata

### Requirement: Scene image event contract coverage
The maintained backend suite SHALL verify that a cached scene-image event is emitted as a client-readable SSE payload for the owning game.

#### Scenario: Consume a cached event once
- **WHEN** an event for an owned game is cached and the event stream is requested with one-shot mode
- **THEN** the first SSE payload preserves the game, week, round, stage, and event type fields

### Requirement: Image ownership failure contract coverage
The maintained backend suite SHALL verify that missing games, foreign games, and missing images do not resolve to usable image resources.

#### Scenario: Request an inaccessible image resource
- **WHEN** a caller resolves a missing or foreign game or image
- **THEN** the router raises a 404 HTTP error
