## ADDED Requirements

### Requirement: Reading requests use explicit story context
The system SHALL create story voice reading requests from an explicit reading context instead of inferring the latest story from a game id alone.

#### Scenario: Read current round story
- **WHEN** the user starts reading the visible current story
- **THEN** the reading request MUST include the current `game_id`, `week`, `round_number`, `stage`, `text_hash`, and visible story text

#### Scenario: Read selected historical round
- **WHEN** the user starts reading while viewing a historical round
- **THEN** the reading request MUST use the selected historical round text and identity
- **AND** it MUST NOT fall back to the latest current story

#### Scenario: Read summary or ending
- **WHEN** the user starts reading a generated summary or ending
- **THEN** the reading request MUST identify the source as summary or ending and include a stable text hash

### Requirement: Voice reading settings are selectable and persisted
The system SHALL allow users to select built-in voice reading settings and reuse those settings for subsequent story reading.

#### Scenario: Select built-in voice
- **WHEN** the user selects a built-in voice color
- **THEN** subsequent reading requests MUST use that voice until the user changes it

#### Scenario: Update auto-read setting
- **WHEN** the user enables or disables auto-read
- **THEN** the setting MUST persist across page reloads for the same authenticated user or active session

#### Scenario: Unsupported voice setting
- **WHEN** a reading request references an unavailable voice
- **THEN** the backend MUST reject the request with a contract-stable error field instead of silently choosing a different voice

### Requirement: Custom voice material is gated by consent and membership
The system SHALL gate uploaded or custom voice synthesis behind explicit consent, validation, and membership eligibility.

#### Scenario: Non-member requests custom voice
- **WHEN** a non-member or unauthenticated user attempts to use uploaded custom voice synthesis
- **THEN** the system MUST require member login or upgrade before enabling that voice

#### Scenario: Upload voice sample
- **WHEN** a member uploads voice material
- **THEN** the system MUST require explicit consent and validation before storing or processing the sample

#### Scenario: Consent missing
- **WHEN** uploaded voice material is submitted without required consent
- **THEN** the system MUST reject the upload and MUST NOT store the sample

### Requirement: Reading queue follows generation attempt boundaries
The system SHALL queue auto-read content only after visible story content reaches a stable generation boundary and SHALL keep queued items in story order.

#### Scenario: Completed story is queued
- **WHEN** auto-read is enabled and a story generation attempt completes
- **THEN** the reading system MUST enqueue the completed visible story once in the same order it appears in gameplay

#### Scenario: Regeneration replaces queued reading
- **WHEN** a regenerated story replaces text for the same round and stage
- **THEN** the reading system MUST cancel or supersede queued reading for the old attempt
- **AND** it MUST read only the regenerated visible story

#### Scenario: Streaming text is still in progress
- **WHEN** story text is still streaming and has not reached completion
- **THEN** auto-read MUST NOT enqueue partial text as a completed reading item

### Requirement: Reading audio assets are persisted and reused
The system SHALL persist generated reading audio metadata and reuse compatible assets for identical text and voice settings.

#### Scenario: Generated audio succeeds
- **WHEN** a reading job generates audio successfully
- **THEN** the system MUST store metadata including source context, normalized text hash, voice id, speed, provider, model version, storage path, duration, status, and creation time

#### Scenario: Compatible audio exists
- **WHEN** a reading request has the same normalized text hash and compatible voice settings as an existing successful asset
- **THEN** the system MUST reuse the existing audio asset instead of submitting a duplicate generation job

#### Scenario: Story text changes
- **WHEN** story text changes because of rewrite or regeneration
- **THEN** the new reading request MUST use a different text hash and MUST NOT reuse audio generated for the old text

### Requirement: Reading playback exposes stable controls and states
The system SHALL expose stable controls and states for story voice playback.

#### Scenario: Start reading
- **WHEN** the user starts reading a supported text source
- **THEN** the UI MUST expose loading or playing state, pause, resume, and stop controls

#### Scenario: Reading job fails
- **WHEN** audio generation or playback fails
- **THEN** the UI MUST show a retryable failed state without blocking story choices, saving, history review, or music controls

#### Scenario: Page reload during pending job
- **WHEN** the page reloads while a reading job is pending
- **THEN** the UI MUST be able to recover the job status from persisted backend state

### Requirement: Story voice reading is covered by immutable no-mock test gates
The system SHALL require test-first coverage for story voice reading across static analysis, imports, contracts, real DB integration, and browser E2E, and these tests SHALL be wired into `test.sh`.

#### Scenario: Tests are written before implementation
- **WHEN** implementation begins for a story voice reading behavior or bug fix
- **THEN** failing tests for the affected layer MUST be added before production code changes

#### Scenario: Tests are wired into test.sh
- **WHEN** `./test.sh all` is executed
- **THEN** story voice reading static, import, contract, real DB, and browser E2E tests MUST run through the existing layer functions

#### Scenario: Tests are not weakened after creation
- **WHEN** a story voice reading test has been added for this change
- **THEN** implementation work MUST NOT skip, mock, delete, or weaken that test to make production code pass

#### Scenario: Full verification gate
- **WHEN** story voice reading implementation is claimed complete
- **THEN** `./test.sh all` MUST pass, including strict mypy, import validation, producer/consumer contract tests, real DB save-read tests, and browser E2E interaction tests
