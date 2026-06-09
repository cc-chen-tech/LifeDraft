## ADDED Requirements

### Requirement: Browser fallback respects selected voice color

When backend TTS audio falls back to browser speech, the frontend SHALL apply the selected story voice color to browser speech synthesis when a matching browser voice is available.

#### Scenario: Male voice selected during browser speech fallback
- **GIVEN** backend reading returns `playback_mode` as `browser_speech`
- **AND** the user has selected `calm_male`
- **AND** the browser exposes a Chinese male speech synthesis voice
- **WHEN** the frontend starts story reading
- **THEN** the created `SpeechSynthesisUtterance` MUST use the matching browser voice
- **AND** the reading state MUST enter `browser_speech` playback.

### Requirement: Voice backend failures fall back without retry delay

Voice-reading API failures SHALL not create a long silent wait before browser speech fallback.

#### Scenario: Backend TTS request returns server unavailable
- **GIVEN** browser speech synthesis is available
- **WHEN** `/voice-reading/read` returns a server error
- **THEN** the frontend MUST NOT retry the voice-reading request
- **AND** the story voice store MUST start browser speech fallback
- **AND** the user MUST not remain in a failed or indefinitely loading reading state.
