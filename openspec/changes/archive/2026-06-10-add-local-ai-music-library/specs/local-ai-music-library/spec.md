## ADDED Requirements

### Requirement: Ready Generated Tracks Are Indexed As Library Entries
The system SHALL make every successfully generated AI music asset eligible for local-library lookup using sanitized music metadata.

#### Scenario: MiniMax generation completes successfully
- **WHEN** a MiniMax music generation job produces a ready playable asset
- **THEN** the system SHALL persist a local-library profile containing normalized mood, scene type, environment, pacing, energy, instruments, negative cues, provider, model, generation settings, duration, loopability, and storage identity
- **AND** the profile SHALL be linked to the generated music asset.

#### Scenario: Generation fails or remains pending
- **WHEN** a generated music asset status is not `ready`
- **THEN** the system SHALL NOT return that asset as a local-library match.

### Requirement: Library Lookup Precedes New MiniMax Generation
The system SHALL check the local AI music library before making a new MiniMax music generation call.

#### Scenario: A compatible local track clears the match threshold
- **WHEN** `/api/music/generate` or `/api/music/generate-async` receives a story brief with a high-confidence local-library match
- **THEN** the system SHALL reuse the local track without calling MiniMax generation
- **AND** the reused track SHALL be inserted through the same future-queue policy as a newly generated track.

#### Scenario: No compatible local track is found
- **WHEN** the local library has no ready playable candidate that clears the configured threshold
- **THEN** the system SHALL continue to the existing MiniMax generation path when AI generation is enabled.

### Requirement: Library Matching Enforces Scene Fit And Negative Cues
The system SHALL reject local-library candidates that conflict with the requesting story's music intent.

#### Scenario: Candidate conflicts with negative cues
- **WHEN** a local-library candidate metadata, title, prompt profile, or instrumentation conflicts with the current brief's negative cues
- **THEN** the system SHALL reject that candidate even if mood or scene fields are similar.

#### Scenario: Candidate has weak scene similarity
- **WHEN** a local-library candidate does not meet the configured fit threshold for mood, scene type, setting, energy, pacing, and instruments
- **THEN** the system SHALL treat the lookup as a miss and avoid reusing the track.

### Requirement: Reused Library Tracks Preserve Playlist Semantics
The system SHALL expose reused local AI tracks through the existing generated-track playlist contract.

#### Scenario: Current song is playing
- **WHEN** a reused local AI track is selected while a NetEase or AI track is currently playing
- **THEN** the playlist SHALL keep the current song unchanged
- **AND** the reused AI track SHALL be inserted into a future queue position.

#### Scenario: Frontend receives a reused library track
- **WHEN** the frontend receives a reused local AI track
- **THEN** the track SHALL include compatible generated-track fields such as `source`, `asset_id`, `provider`, `model`, and playable `url`
- **AND** any reuse metadata SHALL be non-breaking for existing music store consumers.

### Requirement: Source Story Details Are Not Exposed Through Library Reuse
The system SHALL prevent local-library reuse from leaking another game's source story or prompt details to the frontend.

#### Scenario: A track generated for one game is reused in another game
- **WHEN** the system returns a local-library track for a different requesting game
- **THEN** the response SHALL NOT include the source game id, original story text, stored story summary, or original prompt text
- **AND** the displayed title or description SHALL be derived from the requesting story's current music brief or a generic AI music label.

### Requirement: Library Reuse Is Observable
The system SHALL record local-library decisions for quality tuning and debugging.

#### Scenario: Lookup returns a hit
- **WHEN** a local-library candidate is reused
- **THEN** the system SHALL record the selected asset id, match score, decision reason, requesting game id, and updated usage metadata.

#### Scenario: Lookup rejects candidates
- **WHEN** local-library candidates are rejected
- **THEN** the system SHALL record rejection reasons such as stale audio, negative cue conflict, provider/model mismatch, or low scene-fit score.
