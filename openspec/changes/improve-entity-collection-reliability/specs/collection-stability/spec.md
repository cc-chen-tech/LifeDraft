## ADDED Requirements

### Requirement: Durable Entity Add Completes Before Detail Hydration

The collection UI SHALL treat the successful add response as the completion of the blocking user action and SHALL refresh collection details separately without hiding existing data.

#### Scenario: Add response succeeds
- **WHEN** the add endpoint returns the names durably persisted to the game state
- **THEN** the UI MUST clear add loading and recognition selection immediately
- **AND** a subsequent detail refresh MUST run as a non-blocking refresh.

#### Scenario: Persisted entities survive reload
- **WHEN** recognized people, items, or landmarks are added through the production route
- **THEN** loading the game state from the real database MUST return the added entities
- **AND** the add response field names MUST match the frontend consumer contract.
