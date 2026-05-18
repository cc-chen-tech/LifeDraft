## ADDED Requirements

### Requirement: Music URLs Are HTTPS-Safe

Music recommendations used on the HTTPS production site SHALL not expose insecure HTTP media URLs to the browser.

#### Scenario: Provider returns an HTTP audio URL
- **Given** the music provider returns an `http://` audio URL
- **When** the frontend receives a playable track
- **Then** the system SHALL convert it to an HTTPS-safe URL or proxy it
- **And** the browser SHALL not emit mixed-content audio warnings.

### Requirement: Unavailable Media Degrades Without Blocking Gameplay

Music and scene image failures SHALL not block story progression.

#### Scenario: Music service is unavailable
- **Given** the story content has generated successfully
- **When** the music service returns an error or unsuitable track
- **Then** the UI SHALL show music as unavailable or pending
- **And** story choices and continuation controls SHALL remain usable.
