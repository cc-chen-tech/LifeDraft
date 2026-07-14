## ADDED Requirements

### Requirement: Media requests use committed current story context
The system SHALL send media consumers only valid current event or committed result
story context, never a fabricated generation fallback.

#### Scenario: Choice generation fails
- **WHEN** a choice continuation fails and is rejected
- **THEN** no new scene-image or music request MUST be created from a fabricated result
- **AND** previously playable media MUST remain non-blocking.
