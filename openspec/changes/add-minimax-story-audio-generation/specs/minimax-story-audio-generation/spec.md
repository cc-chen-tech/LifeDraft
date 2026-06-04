## ADDED Requirements

### Requirement: MiniMax credentials are configuration-only
The system SHALL configure MiniMax providers only through environment variables or runtime secret configuration, and SHALL NOT require or store MiniMax API keys in repository files.

#### Scenario: MiniMax providers are imported without credentials
- **WHEN** import validation loads MiniMax TTS and music provider modules without `MINIMAX_API_KEY`
- **THEN** the imports MUST succeed
- **AND** provider availability MUST report unavailable until credentials are configured.

#### Scenario: Repository preflight scans MiniMax secret surfaces
- **WHEN** `test.sh preflight` runs for this change
- **THEN** it MUST fail if committed source, tests, OpenSpec artifacts, or frontend files contain a real MiniMax API key literal
- **AND** it MUST allow documented placeholder environment variable names.

### Requirement: MiniMax story TTS generates real provider audio after story completion
The system SHALL use MiniMax-backed TTS to synthesize completed story text into a persisted playable audio asset when the provider is configured and the user requests reading.

#### Scenario: Manual read uses MiniMax audio provider
- **GIVEN** `STORY_TTS_PROVIDER` selects MiniMax and MiniMax credentials are configured
- **AND** a completed story context contains non-empty text
- **WHEN** the user requests story reading
- **THEN** the backend MUST create or reuse a MiniMax narration asset for the story text
- **AND** the response MUST set `playback_mode` to `audio`
- **AND** the response MUST include `audio_url`, `asset_id`, `provider=minimax`, `model`, `media_type`, and `duration_ms`
- **AND** the frontend MUST play the returned audio URL with `HTMLAudioElement`.

#### Scenario: Auto-read waits for completed story text and user opt-in
- **GIVEN** story auto-reading is disabled for the user
- **WHEN** story generation completes
- **THEN** the system MUST NOT automatically call the story reading endpoint.

#### Scenario: Auto-read starts after story generation when enabled
- **GIVEN** story auto-reading is enabled for the user
- **AND** MiniMax TTS is configured
- **WHEN** story generation completes with non-empty final story text
- **THEN** the frontend MUST request story reading using that final story text
- **AND** it MUST NOT request reading from partial streaming fragments.

#### Scenario: MiniMax TTS failure falls back truthfully
- **GIVEN** MiniMax TTS is selected but synthesis fails, times out, or returns invalid audio
- **WHEN** the user requests story reading
- **THEN** the backend MUST return `playback_mode=browser_speech`
- **AND** the response MUST NOT include a deterministic WAV tone URL
- **AND** the frontend MUST read `context.text` through browser speech synthesis.

### Requirement: MiniMax music generation produces story-conditioned instrumental tracks
The system SHALL generate instrumental background music from a bounded story music brief after story generation completes when AI music generation is enabled.

#### Scenario: Story completion schedules AI music generation by default
- **GIVEN** AI music generation is not explicitly disabled
- **AND** a story completes with non-empty story text
- **WHEN** music orchestration runs for the story
- **THEN** it MUST build a bounded `MusicBrief` from the completed story
- **AND** it MUST request MiniMax music generation using an instrumental/background prompt derived from that brief
- **AND** it MUST continue to provide NetEase recommendations without waiting for MiniMax completion.

#### Scenario: Music generation uses compact prompt input
- **GIVEN** a story text is longer than the configured music prompt budget
- **WHEN** the system builds the MiniMax music request
- **THEN** the request MUST include a compressed music brief rather than the full story text
- **AND** the brief MUST include mood, scene, energy or tempo, instrumentation cues, and negative cues.

#### Scenario: Generated music is inserted into future playlist queue
- **GIVEN** MiniMax music generation completes with a playable audio asset
- **AND** the game playlist has a current track
- **WHEN** the generated track is added to the playlist
- **THEN** the current track MUST remain unchanged
- **AND** the generated track MUST be inserted into a future queue slot
- **AND** the playlist item MUST expose `source=ai_generated`, `provider=minimax`, and the generated asset id.

#### Scenario: Generated music failure preserves existing playback
- **GIVEN** MiniMax music generation fails, times out, or returns no playable asset
- **WHEN** the music player state is refreshed
- **THEN** the current track and NetEase recommendation queue MUST remain usable
- **AND** the failure MUST be recorded with provider, model, brief hash, and an error status.

### Requirement: MiniMax generated assets are persisted and reused by generation identity
The system SHALL persist MiniMax narration and music generation metadata so equivalent requests reuse existing ready assets and failures are diagnosable.

#### Scenario: Equivalent TTS request reuses narration asset
- **GIVEN** a ready MiniMax narration asset exists for the same text hash, voice id, speed, provider, model, and audio format
- **WHEN** the same story reading request is made again
- **THEN** the system MUST return or create a ready job pointing to the existing asset
- **AND** it MUST NOT call MiniMax again.

#### Scenario: Equivalent music brief reuses generated music asset
- **GIVEN** a ready MiniMax music asset exists for the same game, brief hash, provider, model, and generation settings
- **WHEN** the same story music generation request is made again
- **THEN** the system MUST reuse the existing generated asset
- **AND** it MUST insert the reusable track through the same playlist queue policy.

#### Scenario: Different provider settings create distinct assets
- **GIVEN** a ready generated asset exists for one MiniMax model or generation setting
- **WHEN** the same story text or music brief is requested with a different model or generation setting
- **THEN** the system MUST create or select an asset matching the requested provider identity
- **AND** it MUST NOT reuse the incompatible asset.

### Requirement: Browser E2E verifies decodable generated audio and UI state
The system SHALL verify generated audio behavior through browser automation by observing playable browser state and visible controls, not physical speaker output.

#### Scenario: Story reading plays provider audio in browser automation
- **GIVEN** a local test provider serves MiniMax-shaped TTS audio through the backend
- **WHEN** browser E2E clicks story read after story completion
- **THEN** the page MUST attach a decodable audio URL to an `HTMLAudioElement`
- **AND** the element MUST enter a playing or ready-to-play state
- **AND** the UI MUST show provider audio reading progress.

#### Scenario: Generated music appears in the player queue
- **GIVEN** a local test provider serves MiniMax-shaped generated music through the backend
- **WHEN** browser E2E completes a story and opens the music player
- **THEN** the player MUST show the current track unchanged
- **AND** it MUST show a future generated MiniMax track in the queue
- **AND** the generated track MUST be playable by the browser.
