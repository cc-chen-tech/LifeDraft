## MODIFIED Requirements

### Requirement: Voice selection remains responsive while settings load
The system SHALL preserve a user's local voice selection when asynchronous settings responses arrive late.

#### Scenario: User changes voice before settings finish loading
- **GIVEN** the story voice settings request is still in flight
- **WHEN** the user selects a different voice
- **AND** the settings request later returns an older `selected_voice_color`
- **THEN** the UI MUST keep the user's local voice selection
- **AND** the next story reading request MUST use the locally selected voice

#### Scenario: User changes voice during active reading
- **WHEN** the user selects a different voice while a story is loading, ready, playing, or paused
- **THEN** the active reading MUST restart or regenerate with the newly selected voice
