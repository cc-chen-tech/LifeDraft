## ADDED Requirements

### Requirement: Recognized collection entities have stable state lifecycle contracts
The maintained backend suite SHALL verify that recognized characters, items, and landmarks are added once to a player state with their collection metadata.

#### Scenario: Duplicate and player identities are ignored
- **WHEN** recognized entity payloads include a known entity or the player name
- **THEN** the collection service SHALL not add duplicate state entries.

### Requirement: Collection deletion protects player identity and cleans linked images
The maintained backend suite SHALL verify that deleting a removable character removes its matching image record while deletion of the player is denied.

#### Scenario: Character image cleanup
- **WHEN** a non-player character with a matching image is deleted
- **THEN** the character state and its matching image record SHALL be removed.

### Requirement: Collection ownership lookup remains fail-closed
The maintained backend suite SHALL verify that a missing or foreign-owned game cannot be returned by the ownership service.

#### Scenario: Foreign game lookup
- **WHEN** a caller requests a game owned by a different user
- **THEN** the service SHALL raise the collection not-found error.

### Requirement: Maintained workflows run collection lifecycle contracts
Both maintained backend workflow lists SHALL include the collection lifecycle contract module in matching order.

#### Scenario: Workflow parity
- **WHEN** the maintained backend workflow lists are compared
- **THEN** the collection lifecycle contract path SHALL occur in both lists at the same position.
