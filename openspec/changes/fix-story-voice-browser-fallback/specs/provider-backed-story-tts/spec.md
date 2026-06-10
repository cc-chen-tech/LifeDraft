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

### Requirement: Browser-provider settings start speech without backend delay

When production settings report browser speech as the active provider and backend audio as disabled, the frontend SHALL start browser speech directly instead of attempting backend audio first.

#### Scenario: Production voice settings disable backend audio
- **GIVEN** `/voice-reading/settings` returns `tts_provider` as `browser`
- **AND** `backend_audio_enabled` is `false`
- **WHEN** the user starts reading the current story
- **THEN** the frontend MUST NOT call `/voice-reading/read`
- **AND** the story voice store MUST enter browser speech playback.

### Requirement: Voice settings loading does not block reading start

Runtime voice settings loading SHALL NOT make the first manual read action or an already locally enabled auto-read action appear silent or unavailable.

#### Scenario: Manual read while settings are still loading
- **GIVEN** `/voice-reading/settings` has not returned yet
- **WHEN** the user selects the story read action
- **THEN** the read action MUST be enabled
- **AND** the frontend MUST start story narration using the current local voice/provider state
- **AND** the later settings response MUST update future voice runtime settings without cancelling the active narration.

#### Scenario: Completed story auto-read while settings are still loading
- **GIVEN** auto-read is already enabled in the local story voice state
- **AND** `/voice-reading/settings` has not returned yet
- **WHEN** a current-story result becomes complete and ready to read
- **THEN** the frontend MUST start narration for the completed story without waiting for the settings response.

### Requirement: Browser voice switching uses the newly selected voice

Changing the selected voice while browser speech is active SHALL restart speech with the new voice color immediately.

#### Scenario: Switch from warm female to calm male
- **GIVEN** browser speech is currently reading with `warm_female`
- **AND** the browser exposes both female and male Chinese voices
- **WHEN** the user selects `calm_male`
- **THEN** the frontend MUST cancel the current utterance
- **AND** the next utterance MUST use the matching male browser voice
- **AND** matching `male` MUST NOT accidentally match the substring inside `female`.
