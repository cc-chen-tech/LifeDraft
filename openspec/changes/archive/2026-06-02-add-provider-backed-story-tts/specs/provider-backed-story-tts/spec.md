## ADDED Requirements

### Requirement: Story reading selects a truthful playback mode

The system SHALL expose whether a story reading request should be played through backend audio or browser speech, and SHALL NOT label a deterministic local tone as provider-backed narration.

#### Scenario: Browser fallback is selected when no backend TTS provider is configured
- **GIVEN** story TTS provider configuration is absent or set to browser fallback
- **WHEN** the frontend requests reading for a valid story context
- **THEN** the backend response MUST set `playback_mode` to `browser_speech`
- **AND** the response MUST include the selected provider and model metadata
- **AND** the response MUST NOT include a deterministic WAV `audio_url`
- **AND** the frontend MUST use the story context text with browser speech synthesis.

#### Scenario: Backend audio is selected only when a TTS audio provider is configured
- **GIVEN** story TTS provider configuration selects a backend audio provider
- **WHEN** the frontend requests reading for a valid story context
- **THEN** the backend response MUST set `playback_mode` to `audio`
- **AND** the response MUST include a stable `audio_url`, `asset_id`, `duration_ms`, `provider`, `model`, and `media_type`
- **AND** the frontend MUST play the returned `audio_url` through an `HTMLAudioElement`.

### Requirement: Provider-backed assets are persisted and reused by synthesis identity

The system SHALL persist generated story narration assets with enough identity to avoid reusing the wrong provider output.

#### Scenario: Same text, voice, speed, provider, and model reuses an existing asset
- **GIVEN** a ready generated voice asset exists for a text hash, voice id, speed, provider, and model
- **WHEN** the same story reading request is made again
- **THEN** the system MUST create a new ready job pointing at the existing asset
- **AND** it MUST NOT create a duplicate asset.

#### Scenario: Different provider or model creates a distinct asset
- **GIVEN** a ready generated voice asset exists for one provider and model
- **WHEN** the same story text is requested through a different provider or model
- **THEN** the system MUST create or use an asset matching the requested provider and model
- **AND** it MUST NOT reuse the old provider/model asset.

### Requirement: OpenAI-compatible TTS provider is isolated behind configuration

The system SHALL support an OpenAI-compatible TTS provider without requiring external network access for local test gates.

#### Scenario: Provider is unavailable without credentials
- **GIVEN** story TTS is configured for the OpenAI-compatible provider without a usable API key
- **WHEN** settings or reading availability is requested
- **THEN** the system MUST report the provider as unavailable
- **AND** reading requests MUST fall back to browser speech without generating a local tone asset.

#### Scenario: Provider module is importable without optional runtime credentials
- **WHEN** import validation tests load the OpenAI-compatible TTS provider module
- **THEN** the import MUST succeed without requiring API credentials
- **AND** credential checks MUST occur only when a synthesis request selects that provider.

### Requirement: Provider-backed story TTS is covered by layered no-mock gates

The system SHALL require test-first coverage for provider-backed story TTS across static analysis, imports, contracts, real DB integration, and browser E2E, and these tests SHALL run through `test.sh`.

#### Scenario: Test gates are wired before implementation is complete
- **WHEN** provider-backed story TTS implementation is claimed complete
- **THEN** `test.sh preflight` MUST validate the new OpenSpec change
- **AND** `test.sh mypy` MUST include provider TTS strict type targets
- **AND** `test.sh imports` MUST include provider import validation
- **AND** `test.sh contract` MUST include provider/playback schema contracts
- **AND** `test.sh db` MUST include provider-backed asset save-read tests
- **AND** `test.sh e2e` MUST include browser verification for backend audio mode and browser speech fallback.
