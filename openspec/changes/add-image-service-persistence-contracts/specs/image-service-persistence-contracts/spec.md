## ADDED Requirements

### Requirement: Image selection honors game ownership and active version
The maintained backend suite SHALL verify that ImageService selects the highest active version for a game and falls back to that game's primary image when an explicit image ID is absent or does not belong to that game.

#### Scenario: Invalid explicit image reference
- **WHEN** a requested player image belongs to a different game
- **THEN** ImageService SHALL return a data URL for the requesting game's primary image and its ID.

### Requirement: Saved image context preserves field precedence
The maintained backend suite SHALL verify that ImageService prefers the latest saved state for character settings and player name, then falls back to the game's initial state.

#### Scenario: State record missing image context
- **WHEN** the latest saved state omits character settings
- **THEN** ImageService SHALL return the equivalent fields from `Game.initial_state`.

### Requirement: Maintained workflows run image service persistence contracts
Both maintained backend workflow lists SHALL include the image service persistence contract path in matching order.

#### Scenario: Workflow parity
- **WHEN** workflow test lists are compared
- **THEN** the image service persistence contract path SHALL occur in both lists at the same position.
