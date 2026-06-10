## MODIFIED Requirements

### Requirement: Completed story text is eligible for automatic reading
The system SHALL automatically request story reading only after a current story is complete, and it SHALL include all completed choice-result phases that still display the current story.

#### Scenario: Auto-read waits for production voice settings
- **GIVEN** automatic reading is enabled
- **AND** a completed current story is ready to read
- **AND** production voice settings are still loading
- **WHEN** the story voice controls mount
- **THEN** the frontend MUST NOT call `/voice-reading/read` yet
- **AND** after settings finish loading, automatic reading MAY start using the configured provider path
- **AND** if settings report browser speech with backend audio disabled, automatic reading MUST start browser speech without calling `/voice-reading/read`.
