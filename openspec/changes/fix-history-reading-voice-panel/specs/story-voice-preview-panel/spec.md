## ADDED Requirements

### Requirement: Story voice appears as a preview until TTS is available
The system SHALL present story voice reading as an unavailable or preview feature when provider-backed TTS is not available, instead of exposing ineffective playback controls as a working feature.

#### Scenario: Normal gameplay story voice panel
- **WHEN** story text is visible in normal gameplay
- **THEN** the story voice panel MUST show a polished preview/unavailable state
- **AND** it MUST NOT expose job ids, raw audio URLs, playback modes, or debug controls

#### Scenario: Historical story voice panel
- **WHEN** story text is visible in history review
- **THEN** the story voice panel MUST clearly indicate the feature is not yet available for historical story reading
- **AND** it MUST NOT encourage the user to start an operation that cannot reliably produce playable audio

### Requirement: Story voice test controls stay opt-in
The system SHALL keep test-only story voice controls hidden from production gameplay unless explicitly enabled by a test prop.

#### Scenario: Test controls disabled
- **WHEN** `showTestControls` is false or omitted
- **THEN** the component MUST NOT render simulation buttons or raw state diagnostics

#### Scenario: Test controls enabled
- **WHEN** `showTestControls` is true
- **THEN** the component MAY render diagnostic controls and state fields needed by regression tests
