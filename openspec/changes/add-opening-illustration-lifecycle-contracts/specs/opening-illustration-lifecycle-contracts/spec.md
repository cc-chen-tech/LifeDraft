## ADDED Requirements

### Requirement: Opening illustration replacement is persisted deterministically
The maintained backend suite SHALL verify that creating an opening illustration deactivates previous opening illustrations and persists the new active record with its generated prompt, storage location, and source metadata.

#### Scenario: Creating a new opening illustration
- **WHEN** the service creates an opening illustration for a game that already has one
- **THEN** the previous record is inactive and the new record is active with its generation metadata

### Requirement: Opening illustration regeneration preserves reference semantics
The maintained backend suite SHALL verify that regeneration gives current illustration bytes priority over player-image fallback and persists the regeneration source fields.

#### Scenario: Regenerating from the current illustration
- **WHEN** current illustration bytes are available
- **THEN** the provider edit request receives a data URL built from those bytes and the new record identifies the prior illustration

#### Scenario: Regenerating without current illustration bytes
- **WHEN** no current illustration record is available and a player image callback is supplied
- **THEN** the provider edit request uses the player image reference
