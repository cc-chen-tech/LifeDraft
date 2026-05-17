## ADDED Requirements

### Requirement: Stale generation never traps the user

The system SHALL recover or expire an in-progress generation state so the player is never left with no story, no options, and no action after refresh.

#### Scenario: Completed event exists after refresh

- **WHEN** the frontend restores an active game while local UI phase is generating
- **AND** the backend active game contains a current event with story text and options
- **THEN** the frontend MUST show the story and options
- **AND** it MUST clear the transient generating phase.

#### Scenario: Generation remains in progress too long

- **WHEN** story or choice generation exceeds the configured long-running threshold
- **THEN** the UI MUST show a clear long-running generation message
- **AND** it MUST provide a retry or continue/recover action.

#### Scenario: No completed event can be recovered

- **WHEN** generation state is stale and no completed story/options exist
- **THEN** the system MUST expire the stale state into a retryable error
- **AND** it MUST NOT keep restoring an endless generating UI after refresh.
