# music-and-media-degradation Specification

## Purpose
TBD - created by archiving change fix-live-gameplay-recovery-collection. Update Purpose after archive.
## Requirements
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

### Requirement: Local AI Music Library Failures Degrade Without Blocking Gameplay
Local AI music library lookup SHALL be optional for playback continuity and MUST NOT block the existing NetEase baseline or MiniMax fallback flow.

#### Scenario: Library lookup fails
- **WHEN** local AI music library lookup raises an error or exceeds its timeout
- **THEN** the system SHALL continue with NetEase playback and the existing MiniMax generation fallback when enabled
- **AND** story continuation controls SHALL remain usable.

#### Scenario: Library hit points to missing audio
- **WHEN** a local-library candidate metadata row exists but its audio file or URL is not playable
- **THEN** the system SHALL reject that candidate
- **AND** the system SHALL continue as if the library lookup missed.

### Requirement: Low-Confidence Music Degrades To Safe Background Playback
Weak story-to-music matches SHALL degrade to safe background music or pending music state rather than surfacing clearly mismatched tracks.

#### Scenario: Candidate pool is playable but mismatched
- **WHEN** the music service has playable candidates but all candidates are rejected by scene-fit or negative-cue checks
- **THEN** the system SHALL return safe instrumental/background fallback recommendations or no music candidate
- **AND** story choices and continuation controls SHALL remain usable.

#### Scenario: Prompt quality is too low for AI generation
- **WHEN** the system cannot build a bounded scene-specific MiniMax prompt with required negative instructions
- **THEN** it SHALL avoid starting a paid generation call for that scene
- **AND** it SHALL keep the NetEase or safe fallback playback path available.

