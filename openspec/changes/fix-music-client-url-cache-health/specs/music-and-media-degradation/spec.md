## MODIFIED Requirements

### Requirement: Unavailable Media Degrades Without Blocking Gameplay

Music and scene image failures SHALL not block story progression.

#### Scenario: Music service is unavailable
- **Given** the story content has generated successfully
- **When** the music service returns an error or unsuitable track
- **Then** the UI SHALL show music as unavailable or pending
- **And** story choices and continuation controls SHALL remain usable.

#### Scenario: Netease music API default endpoint is used in Docker or ECS
- **Given** `NETEASE_MUSIC_API_URL` is not set
- **When** the music client is initialized
- **Then** it SHALL default to `http://music-api:3001`
- **And** it SHALL still normalize an explicit `localhost` URL to `127.0.0.1`.

#### Scenario: Song URL cache protects short-lived playable URLs
- **Given** the music client has already resolved a playable URL for a song
- **When** the same song URL is requested before the cache expires
- **Then** the client SHALL return the cached URL without calling the upstream API
- **And** the cache TTL SHALL be 480 seconds.

#### Scenario: Music API transient failure is retried
- **Given** the Netease music API returns a retryable server error such as 500, 502, or 504, or a transient network error
- **When** the client searches songs or resolves a song URL
- **Then** the client SHALL retry within the configured retry budget
- **And** it SHALL return an empty result or `None` without blocking gameplay if retries are exhausted.

#### Scenario: Music API 503 degrades without retry noise
- **Given** the Netease music API returns HTTP 503
- **When** the client searches songs or resolves a song URL
- **Then** the client SHALL return an empty result or `None` after a single upstream call
- **And** it SHALL not retry the unavailable service.
