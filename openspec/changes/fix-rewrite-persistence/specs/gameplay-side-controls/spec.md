## ADDED Requirements

### Requirement: Rewrite completion persists the rewritten current story

When a user rewrites the current story, the backend SHALL treat the rewritten story as the authoritative current event text for both the active in-memory session and persisted game state.

#### Scenario: Streaming rewrite completes

- **Given** a game has a current event with persisted `current_event_data`
- **When** `/api/games/{game_id}/rewrite-stream` completes with rewritten story text
- **Then** the current event description SHALL be replaced with the rewritten story
- **And** `player_state.current_event_data.event_description` SHALL be replaced with the rewritten story
- **And** the game state SHALL be saved after the mutation

#### Scenario: Non-streaming rewrite completes

- **Given** a game has a current event with persisted `current_event_data`
- **When** `/api/games/{game_id}/rewrite` returns a rewritten story
- **Then** the current event description SHALL be replaced with the rewritten story
- **And** `player_state.current_event_data.event_description` SHALL be replaced with the rewritten story
- **And** the game state SHALL be saved after the mutation
