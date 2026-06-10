## ADDED Requirements

### Requirement: Game Side Panels Are Mutually Exclusive

The game play page SHALL NOT render multiple side-panel surfaces for primary navigation controls at the same time.

#### Scenario: Collection opens while history state is still open

- **GIVEN** the history side panel is open from the gameplay hook state
- **WHEN** the user opens the collection panel
- **THEN** the history side panel MUST be hidden before the collection panel is rendered
- **AND** the page MUST NOT display history and collection side panels simultaneously.

#### Scenario: History opens while collection is open

- **GIVEN** the collection side panel is open
- **WHEN** the user opens the history panel
- **THEN** the collection side panel MUST close
- **AND** only the history side panel may remain visible.
