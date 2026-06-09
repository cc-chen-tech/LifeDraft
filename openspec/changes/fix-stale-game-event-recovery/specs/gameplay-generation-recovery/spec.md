## ADDED Requirements

### Requirement: Stale persisted game ids do not start event generation

When the play page initializes from a persisted or URL-provided game id and the server confirms that game is not found, the frontend SHALL clear the stale session and navigate away instead of attempting to generate a new event for that id.

#### Scenario: Initial sync returns not found
- **Given** the play page has a persisted game id
- **When** initial state synchronization for that game fails with 404 or not-found
- **Then** the frontend SHALL clear the local game session
- **And** it SHALL navigate back to the home page
- **And** it SHALL NOT request `/api/games/{game_id}/event` for that stale id

#### Scenario: Stale-session redirect is already in progress
- **Given** the play page already checked a concrete game id
- **And** stale-session handling clears that game id before navigation completes
- **When** the play page observes that no game id remains
- **Then** it SHALL NOT issue a new `/api/games/active` recovery request from that same redirect path
