## ADDED Requirements

### Requirement: Active-game recovery rejects cross-user pointers
The maintained backend suite SHALL verify with the real database that an
active-game pointer referencing another user's game is not returned to the
requesting user and is cleared durably.

#### Scenario: Stale pointer references a different user's game
- **WHEN** a user's persisted active-game ID references a game owned by another
  user
- **THEN** active-game lookup returns no game and a fresh database read shows
  the pointer cleared
