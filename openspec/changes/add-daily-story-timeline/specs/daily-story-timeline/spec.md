## ADDED Requirements

### Requirement: Daily timeline is the authoritative clock
Daily-mode games SHALL derive their date and progress from an ISO Gregorian `start_date` and zero-based `day_index`, and SHALL end after 672 completed days.

#### Scenario: Current timeline is returned
- **WHEN** a daily game state is requested
- **THEN** the response MUST include version, start date, current date, day number, completed days, week number, weekday, and total days

#### Scenario: Calendar boundary advances
- **WHEN** a choice commits on the last day of a month, year, or leap-year February
- **THEN** the next current date MUST be the next valid Gregorian date

#### Scenario: Game completes
- **WHEN** the choice for day 672 commits
- **THEN** the game MUST enter its ending state and MUST NOT generate day 673

### Requirement: Legacy saves migrate idempotently
The system SHALL upgrade legacy `(week, round)` saves without modifying historical prose or inventing unplayed days.

#### Scenario: Legacy weekly history migrates
- **WHEN** a legacy save is migrated
- **THEN** its era year's first Monday MUST anchor week one and its Monday, midweek, and weekend entries MUST map to Monday, Wednesday, and Sunday

#### Scenario: Migration repeats
- **WHEN** migration runs again on a timeline-v2 save
- **THEN** the timeline and day history MUST remain unchanged

### Requirement: Daily choices are versioned and idempotent
The system SHALL accept a generated option only for the current event id and revision and SHALL commit its effects, history, and day advancement at most once.

#### Scenario: Current option commits
- **WHEN** a request submits the current event id, revision, and valid option index
- **THEN** the system MUST apply the option effects, persist one day record, advance one day, and return the next timeline

#### Scenario: Stale option is submitted
- **WHEN** a request references a replaced event revision
- **THEN** the system MUST reject it without changing resources, history, or date

#### Scenario: Completed request is delivered twice
- **WHEN** the same accepted event choice is retried
- **THEN** the system MUST return the stored settlement without applying effects or advancing again

### Requirement: Daily scheduled events use exact dates
Daily-mode scheduled events SHALL use an exact ISO `scheduled_date` and Gregorian arithmetic for relative expressions.

#### Scenario: Tomorrow crosses a boundary
- **WHEN** an event is scheduled for tomorrow on the final day of a month or year
- **THEN** its scheduled date MUST be the next Gregorian date

#### Scenario: Scheduled date arrives
- **WHEN** the daily generator runs on a pending scheduled event's date
- **THEN** that event MUST be eligible to drive the day's story
