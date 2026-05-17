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

#### Scenario: Stream completes without a playable event

- **WHEN** an event stream completes without options
- **OR** it completes with options but no recoverable story body
- **THEN** the frontend MUST enter a retryable error state
- **AND** it MUST NOT leave the player in the generating phase.

### Requirement: Opening page uses the same effective character source as recovery flow

The opening story page SHALL use resolved character data (store data or injected recovery/test data) consistently for validation and request payloads.

#### Scenario: Store is incomplete but resolved data is available

- **WHEN** `/story/opening` receives resolved character data from injected/recovered source
- **AND** local store fields are temporarily empty during hydration/recovery
- **THEN** opening story generation MUST use the resolved data for request payload
- **AND** the page MUST NOT show the "缺少角色数据" error.
