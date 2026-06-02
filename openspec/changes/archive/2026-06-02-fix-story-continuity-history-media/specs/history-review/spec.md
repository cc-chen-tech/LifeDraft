## ADDED Requirements

### Requirement: History review remains pinned to the selected round
The system SHALL keep history review pinned to the selected historical round until the user explicitly returns to the current round.

#### Scenario: Select historical round while current story updates
- **WHEN** the user selects a historical round while current story generation or streaming continues
- **THEN** the visible story text MUST remain the selected historical round text

#### Scenario: Return to current round
- **WHEN** the user activates return-to-current
- **THEN** the visible story text and options MUST switch back to the latest current gameplay state

### Requirement: History review is read-only
The system SHALL prevent gameplay choices and story-editing actions from mutating a historical round view.

#### Scenario: Viewing historical round
- **WHEN** the user is viewing a historical round
- **THEN** current-round choices MUST be hidden or disabled and historical content MUST NOT be submitted as a current choice

### Requirement: Historical scene images match the selected round
The system SHALL display scene images that match the selected historical `game_id`, `week`, `round`, and `stage`.

#### Scenario: Historical image exists
- **WHEN** the selected historical round has a scene image
- **THEN** the image displayed MUST be the image for that selected week and round

#### Scenario: Historical image missing
- **WHEN** the selected historical round has no scene image
- **THEN** the UI MUST show a generate-image affordance for that selected round without showing the current round image

#### Scenario: Switch historical rounds
- **WHEN** the user selects a different historical round
- **THEN** the text and scene image MUST update together to the newly selected round

### Requirement: Scene images are keyed by stage
The system SHALL distinguish `event` and `result` scene images for both current and historical rounds.

#### Scenario: Current event phase
- **WHEN** the current phase is showing an event before choice resolution
- **THEN** the current scene display SHOULD prefer the `event` stage image for the current round

#### Scenario: Current result phase
- **WHEN** the current phase is showing the result after a choice
- **THEN** the current scene display SHOULD show both available event/result context or prefer the `result` stage image where a single image is required

### Requirement: Missing scene images auto-generate from persisted state
The scene-image endpoint SHALL use persisted game-state snapshots to generate missing scene images.

#### Scenario: Scene image missing but current event persisted
- **WHEN** a scene image is requested by `game_id`, `week`, `round_number`, and `stage`
- **AND** no scene image exists yet
- **AND** the latest persisted game state contains `current_event_data.event_description`
- **THEN** the backend MUST trigger background generation from `game_states.state_json` and return `202`

#### Scenario: Game row has no player_state column
- **WHEN** the scene-image endpoint inspects game persistence
- **THEN** it MUST NOT access a nonexistent `Game.player_state` attribute
