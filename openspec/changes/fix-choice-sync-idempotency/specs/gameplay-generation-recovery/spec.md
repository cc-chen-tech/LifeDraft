# gameplay-generation-recovery Specification Delta

## ADDED Requirements

### Requirement: Duplicate Choice Sync Returns Persisted Result

The system SHALL treat duplicate non-streaming choice fallback requests as
idempotent after the first request has already saved the round result.

#### Scenario: Duplicate choice-sync after saved result
- **GIVEN** a saved game has no current event because the latest sync fallback choice already completed
- **AND** the latest round history contains the persisted continuation, summary, effects, and warnings
- **WHEN** the client sends another `choice-sync` request for that game
- **THEN** the endpoint SHALL return HTTP 200 with the persisted choice result fields
- **AND** it SHALL NOT return `choice_already_processed`

#### Scenario: Duplicate custom-choice-sync after saved result
- **GIVEN** a saved game has no current event because the latest custom sync fallback choice already completed
- **AND** the latest round history contains the persisted continuation, summary, effects, and warnings
- **WHEN** the client sends another `custom-choice-sync` request for that game
- **THEN** the endpoint SHALL return HTTP 200 with the persisted choice result fields
- **AND** it SHALL NOT return `choice_already_processed`
