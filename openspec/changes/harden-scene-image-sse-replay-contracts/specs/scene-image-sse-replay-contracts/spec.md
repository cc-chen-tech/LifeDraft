## ADDED Requirements

### Requirement: Scene image SSE replays latest events only for the requested game
The backend suite SHALL verify that scene image events are keyed by game, week,
round, and stage; replacing the same key SHALL expose only the newest payload, and
an authenticated replay SHALL not include another game's cached event.

#### Scenario: Replay cached terminal events for one owned game
- **WHEN** a game has a superseded event and a second event at another stage
- **AND** another game's event is also cached
- **THEN** the authenticated `once=true` stream emits the two current events for
  the requested game only
- **AND** each replayed event retains its frontend-required identity and terminal
  fields
