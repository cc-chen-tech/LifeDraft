## ADDED Requirements

### Requirement: Persisted game routes enforce owner-scoped lifecycle
The maintained backend suite SHALL verify that a real user can list and delete
only its persisted game records.

#### Scenario: Owned game is listed and deleted
- **WHEN** a user owns a persisted game with saved state
- **THEN** the router MUST list its display fields and delete the game for that
  same user.

### Requirement: Pre-play character settings persist their authoritative fields
The maintained backend suite SHALL verify that late character settings merge
into a real unplayed game and synchronize a valid initial wealth value.

#### Scenario: Settings arrive before first round
- **WHEN** an unplayed saved state receives nested settings and initial wealth
- **THEN** the persisted state MUST retain prior nested fields and use the new
  wealth as its opening balance.

### Requirement: Narrative style settings round-trip through storage
The maintained backend suite SHALL verify that a valid style can be stored and
read for an owned game.

#### Scenario: Style update succeeds
- **WHEN** an owner updates a game to a known narrative style
- **THEN** the subsequent read MUST return that style identifier and its
  manifest name.
