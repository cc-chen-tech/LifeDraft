## MODIFIED Requirements

### Requirement: Unavailable Media Degrades Without Blocking Gameplay

Music and scene image failures SHALL not block story progression.

#### Scenario: Music service is unavailable
- **Given** the story content has generated successfully
- **When** the music service returns an error or unsuitable track
- **Then** the UI SHALL show music as unavailable or pending
- **And** story choices and continuation controls SHALL remain usable.

#### Scenario: Music recommendation upstream times out
- **Given** the client requests `/api/music/recommend` after story content is available
- **When** the story-to-music analysis path times out or raises an unexpected upstream error
- **Then** the API SHALL return HTTP 200 with a schema-valid music recommendation response
- **And** the response SHALL contain an empty `songs` list instead of a gateway or internal-server error
- **And** the response SHALL include safe instrumental fallback recommendation fields for consumers that expect `keywords`, `mood`, `scene_type`, and `music_brief`.
