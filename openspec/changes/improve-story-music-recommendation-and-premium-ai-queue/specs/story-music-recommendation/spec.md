## ADDED Requirements

### Requirement: Music recommendations use a structured story music brief
The system SHALL convert story context into a structured music brief before searching or generating music.

#### Scenario: Brief includes narrative and musical intent
- **WHEN** the backend analyzes story text for music
- **THEN** it MUST produce structured fields for mood, scene type, era or environment, pacing, energy, suitable instruments, search queries, negative cues, and a generation prompt placeholder

#### Scenario: Brief has safe defaults
- **WHEN** AI brief analysis fails or returns malformed output
- **THEN** the system MUST fall back to safe instrumental background-music defaults and continue through the Netease recommendation path

### Requirement: Netease remains the immediate baseline provider
The system SHALL use Netease recommendations as the immediate music source for all users.

#### Scenario: Non-member requests music
- **WHEN** a non-member requests story music
- **THEN** the system MUST return Netease-based recommendations and MUST NOT enqueue AI music generation

#### Scenario: Member requests music
- **WHEN** a member requests story music
- **THEN** the system MUST still return immediate Netease-based recommendations without waiting for AI music generation

#### Scenario: AI music feature disabled
- **WHEN** the AI music feature flag is disabled
- **THEN** the system MUST behave as Netease-only even for members

### Requirement: Netease results are matched and ranked against the music brief
The system SHALL use the music brief to improve Netease search query construction and result ordering.

#### Scenario: Query construction uses multiple brief dimensions
- **WHEN** search queries are built
- **THEN** they SHOULD combine relevant mood, era, scene type, pacing, energy, and instrument cues instead of relying only on generic mood words

#### Scenario: Incompatible results are deprioritized
- **WHEN** Netease returns playable results
- **THEN** the system SHOULD rank results that match the brief above results that only loosely match generic keywords

### Requirement: Queue updates do not interrupt current playback
The system SHALL keep background music playback smooth when new recommendations or generated tracks arrive.

#### Scenario: Current song exists
- **WHEN** new Netease recommendations arrive
- **THEN** the current song MUST remain unchanged and only future queue entries MAY be updated

#### Scenario: Generated track completes
- **WHEN** an AI-generated track finishes in the background
- **THEN** the system MUST insert it into a future queue position and MUST NOT switch away from the current song

#### Scenario: Near-term queue stability
- **WHEN** the queue already has at least one upcoming song
- **THEN** generated tracks SHOULD be inserted after the first upcoming song unless user settings or explicit actions request stronger AI mixing

### Requirement: AI-generated music is a premium queue supplement
The system SHALL treat AI-generated music as an additional member benefit, not as the primary recommendation source.

#### Scenario: Member with AI music enabled
- **WHEN** a member has AI music generation enabled
- **THEN** the system MAY enqueue a background generation job using the current music brief after returning immediate Netease recommendations

#### Scenario: Generated track is available
- **WHEN** a background-generated track is ready and still relevant to the current or recent music brief
- **THEN** the system MUST add it to the future queue with `source` metadata identifying it as AI-generated

#### Scenario: Generated track is no longer relevant
- **WHEN** a generated track completes after the story context has materially changed
- **THEN** the system SHOULD persist the asset for reuse but MAY skip immediate queue insertion

### Requirement: Generated music defaults to instrumental ambience loops
The system SHALL default generated music prompts to instrumental or ambience loop tracks.

#### Scenario: Standard gameplay generation
- **WHEN** the system creates a generation prompt for gameplay background music
- **THEN** the prompt MUST request instrumental or ambience music and SHOULD avoid vocals or lyrics by default

#### Scenario: Future vocal mode
- **WHEN** a future feature requests lyric or vocal music
- **THEN** it MUST be represented as an explicit mode rather than the default gameplay background behavior

### Requirement: Generated music assets are persisted and reused
The system SHALL persist generated music asset metadata and storage references so equivalent scenes can reuse existing audio.

#### Scenario: Generated asset succeeds
- **WHEN** AI music generation succeeds
- **THEN** the system MUST store metadata including provider, model, music brief, prompt, brief hash, storage path, duration, loopability, status, and creation time

#### Scenario: Equivalent brief already has an asset
- **WHEN** a member scene resolves to an existing compatible brief/provider hash
- **THEN** the system SHOULD reuse the existing generated asset instead of submitting a duplicate generation job

### Requirement: AI generation failure falls back to Netease
The system SHALL preserve music availability when AI music generation fails.

#### Scenario: Generation fails
- **WHEN** an AI music generation job fails, times out, or returns unusable audio
- **THEN** the system MUST record the failure and keep or refresh Netease recommendations for the queue

#### Scenario: Provider unavailable
- **WHEN** the configured AI music provider is unavailable
- **THEN** member playback MUST continue through the Netease path without blocking gameplay
