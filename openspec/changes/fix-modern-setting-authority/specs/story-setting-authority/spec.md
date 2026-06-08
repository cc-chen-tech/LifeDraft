## ADDED Requirements

### Requirement: Accepted world settings author initial game state
The system SHALL include the world setting accepted by the player in the first game creation request.

#### Scenario: Accept generated world before game creation
- **WHEN** the player accepts generated world content on the world creation step
- **AND** no game has been created yet
- **THEN** the `/api/games` request MUST include that accepted world content in `character_settings.world`

### Requirement: Auto-matched narrative style is recoverable
The system SHALL persist the narrative style selected during game initialization into the initial recoverable game state.

#### Scenario: Initialize game without explicit narrative style
- **WHEN** character settings do not include `narrative_style_id`
- **AND** the initializer auto-matches a style with sufficient confidence
- **THEN** the saved `initial_state` MUST include `narrative_style_id`
- **AND** the loaded game loop MUST restore the same `narrative_style_id`
