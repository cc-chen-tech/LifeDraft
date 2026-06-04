## ADDED Requirements

### Requirement: MiniMax TTS provider is isolated behind provider configuration
The system SHALL support a MiniMax story TTS provider without requiring external network access or credentials for import, static analysis, or normal local test gates.

#### Scenario: MiniMax provider unavailable without credentials
- **GIVEN** story TTS is configured for MiniMax without a usable MiniMax API key
- **WHEN** settings or reading availability is requested
- **THEN** the system MUST report the provider as unavailable
- **AND** reading requests MUST fall back to browser speech without generating a local tone asset.

#### Scenario: MiniMax provider module is importable without credentials
- **WHEN** import validation tests load the MiniMax TTS provider module
- **THEN** the import MUST succeed without requiring API credentials
- **AND** credential checks MUST occur only when a synthesis request selects that provider.

### Requirement: MiniMax TTS audio mode is truthful provider playback
The system SHALL return backend audio playback only when MiniMax synthesis produced or reused a real provider-compatible audio asset.

#### Scenario: MiniMax backend audio response contains provider identity
- **GIVEN** story TTS provider configuration selects MiniMax
- **AND** MiniMax synthesis succeeds or a matching ready MiniMax asset exists
- **WHEN** the frontend requests reading for a valid story context
- **THEN** the backend response MUST set `playback_mode` to `audio`
- **AND** the response MUST include `provider=minimax`, `model`, `asset_id`, `audio_url`, `duration_ms`, and `media_type`
- **AND** the frontend MUST play the returned `audio_url` through an `HTMLAudioElement`.

#### Scenario: MiniMax does not mask failures as fake audio
- **GIVEN** story TTS provider configuration selects MiniMax
- **AND** MiniMax synthesis does not produce a valid audio asset
- **WHEN** the frontend requests reading for a valid story context
- **THEN** the backend response MUST set `playback_mode` to `browser_speech`
- **AND** the response MUST NOT include a deterministic WAV `audio_url`
- **AND** the frontend MUST use the story context text with browser speech synthesis.
