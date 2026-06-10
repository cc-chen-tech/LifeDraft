## ADDED Requirements

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
