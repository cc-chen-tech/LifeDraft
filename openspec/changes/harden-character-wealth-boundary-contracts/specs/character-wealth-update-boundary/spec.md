## ADDED Requirements

### Requirement: Late character wealth does not overwrite played-game balance
The character-settings update contract MUST persist late-generated wealth metadata without resetting the saved wealth or wealth ledger when the game has already played a round.

#### Scenario: Late wealth arrives after gameplay
- **WHEN** an authenticated owner updates character settings containing initial wealth after a state has a played round
- **THEN** the endpoint saves the merged character settings while preserving the existing balance and ledger
