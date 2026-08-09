## ADDED Requirements

### Requirement: Collection responses preserve frontend fields from owned state and images
The maintained backend suite SHALL verify that collection responses preserve item
and landmark lifecycle fields, choose the latest active image for the requested
game, and do not expose images belonging to another game.

#### Scenario: Build a collection from persisted image versions
- **WHEN** an owned game has active and inactive entity image versions and another
  game has an entity with the same name
- **THEN** the response returns the owned active image and all required entity
  fields
- **AND** missing landmark images remain explicitly ungenerated

### Requirement: Collection ownership rejects another user
The maintained backend suite SHALL verify that collection service ownership checks
reject an existing game when requested by another user.

#### Scenario: Intruder checks an existing game
- **WHEN** a user does not own the requested game
- **THEN** the service raises the same not-found ownership error used for absent games
