## ADDED Requirements

### Requirement: Music playback coordinates with story voice reading
The system SHALL coordinate background music playback with story voice playback so narration remains intelligible and user music intent is preserved.

#### Scenario: Reading starts while music is playing
- **WHEN** story voice reading starts while background music is playing
- **THEN** the music system MUST duck or pause background music according to the configured coordination policy

#### Scenario: Reading ends after automatic ducking
- **WHEN** story voice reading ends after the system automatically ducked or paused music
- **THEN** the music system MUST restore the prior music state unless the user manually changed playback during reading

#### Scenario: User changes music during reading
- **WHEN** the user manually pauses, resumes, skips, or changes music while story voice reading is active
- **THEN** the music system MUST preserve the user's latest music intent after reading ends

#### Scenario: Music unavailable
- **WHEN** no background music is loaded or music playback is unavailable
- **THEN** story voice reading MUST still work without requiring a music player state
