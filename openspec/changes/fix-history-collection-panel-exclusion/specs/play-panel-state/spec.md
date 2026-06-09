## ADDED Requirements

### Requirement: Play Page Panel Mutual Exclusion

The play page MUST keep modal side panels mutually exclusive when users switch between collection and history.

#### Scenario: Opening collection closes history

- **GIVEN** the history panel is visible
- **WHEN** the user opens collection
- **THEN** the collection panel is visible
- **AND** the history panel is no longer visible

#### Scenario: Opening history closes collection

- **GIVEN** the collection panel is visible
- **WHEN** the user opens history
- **THEN** the history panel is visible
- **AND** the collection panel is no longer visible
