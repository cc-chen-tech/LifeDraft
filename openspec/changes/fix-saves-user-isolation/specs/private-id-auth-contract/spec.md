## ADDED Requirements

### Requirement: Saved Game List Is User-Isolated
The authenticated saved-game list endpoint SHALL return only unfinished games owned by the authenticated user.

#### Scenario: Authenticated user lists saves with another user's games in the database
- **GIVEN** the database contains saved games for user A and user B
- **WHEN** user A requests `GET /api/games`
- **THEN** the response MUST include only user A's games
- **AND** the response MUST NOT include user B's game ids, names, or progress metadata.

### Requirement: Saved Game Load Enforces Ownership
The saved-game load endpoint SHALL reject attempts to load a game owned by another user.

#### Scenario: Authenticated user loads another user's game id
- **GIVEN** the database contains a saved game owned by user B
- **WHEN** user A requests `GET /api/games/{game_id}` for user B's game
- **THEN** the API MUST return a not-found or forbidden response
- **AND** the response MUST NOT include user B's player state or story progress.

### Requirement: Saves Page Does Not Render Stale Save Lists
The saves page SHALL only render save cards for the currently authenticated session.

#### Scenario: Unauthenticated page state contains stale saved games
- **GIVEN** the client store still contains saved games from a previous session
- **AND** the current user is not authenticated
- **WHEN** the user opens `/saves`
- **THEN** the page MUST NOT render those stale save cards
- **AND** the page MUST NOT request authenticated save loading actions for that stale list.
