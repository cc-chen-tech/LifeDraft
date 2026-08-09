## ADDED Requirements

### Requirement: Saved-game restoration preserves the newest owned state
The maintained backend suite SHALL verify that saved-game loading selects the most
recent snapshot for the owner, supplies compatibility fields from the initial
state when an old snapshot lacks them, and rejects another user.

#### Scenario: Restore an owned game with an older-shaped latest snapshot
- **WHEN** a game has two persisted snapshots and the latest omits identity fields
- **THEN** loading returns the latest gameplay fields with compatible identity
  fields from the initial state
- **AND** a different user cannot load or restore the game

### Requirement: Session restoration stores only the owner's recovered game loop
The maintained backend suite SHALL verify that successful database restoration
creates a user-scoped in-memory session that can be removed cleanly.

#### Scenario: Restore then remove an owned session
- **WHEN** an owner restores a persisted game through SessionService
- **THEN** the returned session contains the latest player state and is scoped to
  that owner
- **AND** removing it makes the in-memory lookup empty
