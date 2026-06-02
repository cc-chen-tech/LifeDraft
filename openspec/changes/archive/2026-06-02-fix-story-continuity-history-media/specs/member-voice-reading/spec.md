## ADDED Requirements

### Requirement: Member login supports phone number identity
The system SHALL support member login with a phone-number-based identity flow before member-only voice features are used.

#### Scenario: Voice feature requires member session
- **WHEN** a non-member or unauthenticated user attempts to access member voice reading
- **THEN** the system MUST prompt for member login before enabling the feature

### Requirement: Story reading supports selectable voice colors
The system SHALL allow members to choose from available voice colors for story reading.

#### Scenario: Select built-in voice
- **WHEN** a member selects a built-in voice color
- **THEN** story reading MUST use that voice for subsequent playback until changed

### Requirement: Members can upload a voice for synthesis
The system SHALL define a path for members to upload voice material for synthesis, subject to consent and safety checks.

#### Scenario: Upload voice sample
- **WHEN** a member uploads a voice sample
- **THEN** the system MUST store or process it only after required consent and validation gates pass

### Requirement: Auto-read advances with story progression
The system SHALL support an auto-read mode that reads new story content as it becomes available.

#### Scenario: New story content streamed
- **WHEN** auto-read is enabled and new story content is displayed
- **THEN** the reading system MUST queue or play the new content in story order
