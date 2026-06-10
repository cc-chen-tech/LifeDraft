## ADDED Requirements

### Requirement: Music Brief Captures Scene-Fit Inputs
The system SHALL derive a structured scene-fit profile from story text and available character settings before selecting or generating music.

#### Scenario: Story contains a recognizable scene context
- **WHEN** a story describes a recognizable context such as modern workplace conflict, suspense, recovery, family conflict, romance, action, or reflective ending
- **THEN** the music brief or scene-fit profile SHALL include normalized scene type, setting/environment, mood, pacing, energy, instrumentation priorities, and negative cues.

#### Scenario: LLM analysis is generic
- **WHEN** LLM-provided music analysis is missing or too generic for an obvious scene
- **THEN** deterministic context enrichment SHALL supply safer scene-specific music fields before search or generation.

### Requirement: Candidates Receive Explainable Fit Scores
The system SHALL score music candidates against the current scene-fit profile before selecting them for playback or reuse.

#### Scenario: NetEase candidates are ranked
- **WHEN** NetEase search returns playable candidates
- **THEN** each candidate considered for the playlist SHALL be scored using fit dimensions such as mood, scene type, setting, energy, pacing, instruments, and negative cues
- **AND** lower-scoring or rejected candidates SHALL NOT outrank clearly compatible background candidates.

#### Scenario: AI-generated or local-library candidates are considered
- **WHEN** a generated or local-library AI track is considered for insertion
- **THEN** the system SHALL apply the same scene-fit and negative-cue checks before selecting it.

### Requirement: MiniMax Prompts Are Structured Scene Directions
The system SHALL build MiniMax music prompts as bounded structured English music directions.

#### Scenario: Prompt is built for a story scene
- **WHEN** the system prepares a MiniMax music generation request
- **THEN** the prompt SHALL include compact story context, primary mood, scene action, setting texture, pacing or tempo, energy, instrumentation priorities, loop/background constraints, and negative instructions
- **AND** the prompt SHALL remain within the configured prompt character budget.

#### Scenario: Negative cues are present
- **WHEN** the music brief contains negative cues such as vocals, lyrics, dominant pop singing, romance pop, dance beats, or scene-specific mismatch cues
- **THEN** the prompt SHALL translate those cues into explicit English negative instructions.

### Requirement: Low-Confidence Matches Use Safe Fallbacks
The system SHALL avoid surfacing obviously mismatched music when scene-fit confidence is low.

#### Scenario: No candidate clears the fit threshold
- **WHEN** no NetEase, local-library, or generated candidate clears the configured scene-fit threshold
- **THEN** the system SHALL fall back to safe instrumental/background recommendations or keep music pending instead of selecting an obviously mismatched track.

#### Scenario: Candidate matches negative cues
- **WHEN** a candidate conflicts with required negative cues
- **THEN** the system SHALL reject that candidate regardless of positive score.

### Requirement: Quality Regressions Are Covered By Offline Fixtures
The system SHALL include offline fixtures for known music mismatch classes and scene types.

#### Scenario: Regression fixture is evaluated in CI
- **WHEN** backend music contract tests run
- **THEN** fixture stories SHALL verify expected brief fields, prompt content, candidate rejection, and fit-score thresholds without calling NetEase or MiniMax.

### Requirement: Matching Diagnostics Preserve Existing Contracts
The system SHALL make scene-matching decisions inspectable without breaking existing music consumers.

#### Scenario: Diagnostics are emitted
- **WHEN** a recommendation, local-library reuse, or MiniMax generation decision is made
- **THEN** the system SHALL record sanitized diagnostics such as fit score, prompt version, selected strategy, and rejection reason
- **AND** existing response fields used by the frontend music player SHALL remain compatible.
