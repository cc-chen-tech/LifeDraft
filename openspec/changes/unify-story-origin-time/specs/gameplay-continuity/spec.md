## ADDED Requirements

### Requirement: Daily gameplay begins from the canonical story origin
New daily games SHALL initialize `timeline.start_date` and `PlayerState.age` from
the validated canonical story origin while retaining `start_date + day_index` as
the gameplay time authority.

#### Scenario: First story day is generated
- **WHEN** a character with origin date 2028-02-29 and starting age 20 starts play
- **THEN** day one is dated 2028-02-29 and the player age is 20

### Requirement: Played origins are immutable
The gameplay service SHALL NOT permit story-origin mutation after the first
playable daily event exists or any story day has been completed.

#### Scenario: Origin edit follows day-one generation
- **WHEN** the day-one event has been generated and an origin edit is requested
- **THEN** the service returns `story_origin_locked` without altering the event,
  timeline, age, settings, or history

### Requirement: Completed-day aging is unchanged
Story-origin unification SHALL preserve age increments at each 365 completed
story days rather than introducing Gregorian birthday progression.

#### Scenario: Campaign crosses the first age milestone
- **WHEN** a player completes story day 365
- **THEN** the player age increases exactly once regardless of leap-day or
  calendar-year boundaries
