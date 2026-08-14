## ADDED Requirements

### Requirement: Story origin is generated and replaced atomically
The system SHALL generate the exact start date, starting age, era description,
life-stage description, and world context as one validated `story_origin`
candidate and SHALL NOT expose partial replacements.

#### Scenario: Initial origin generation succeeds
- **WHEN** a player with valid identity inputs requests a story origin
- **THEN** the system returns a legal Gregorian start date, a valid starting age,
  non-empty narrative fields, and revision 1

#### Scenario: Feedback candidate is invalid
- **WHEN** a regenerated candidate has an invalid date, missing field, or conflicts
  with an explicit date, year, or age in the feedback
- **THEN** the system rejects the candidate and preserves the entire previous
  origin

### Requirement: Birth year is compatibility-only
The system SHALL NOT generate or display birth year as part of the canonical
story origin and SHALL derive it only when projecting legacy compatibility data.

#### Scenario: Origin is projected for a legacy consumer
- **WHEN** a valid origin dated 2026 with starting age 28 is projected
- **THEN** the compatibility age may contain birth year 1998 while the canonical
  origin and user-facing display contain no birth year

### Requirement: Unplayed draft origin uses compare-and-swap replacement
The system SHALL replace an owned unplayed draft origin only when the expected
revision matches and SHALL persist the rebase before reporting success.

#### Scenario: Draft origin replacement succeeds
- **WHEN** an unplayed day-zero game receives a valid candidate with the current
  expected revision
- **THEN** the system increments the revision, rebuilds the day-zero timeline and
  starting age, clears time-dependent settings, and saves all changes atomically

#### Scenario: Draft replacement uses a stale revision
- **WHEN** a draft replacement carries a revision older than the stored origin
- **THEN** the system returns a conflict and leaves the saved state unchanged

#### Scenario: Gameplay has begun
- **WHEN** a game has a current day event, completed day history, or an advanced
  day index and receives an origin replacement
- **THEN** the system rejects it with `story_origin_locked` and changes nothing

### Requirement: Origin revision fences dependent asynchronous work
The system SHALL publish background settings and character media only when their
captured origin revision still matches the current origin.

#### Scenario: Old image finishes after origin replacement
- **WHEN** a character image generated for an earlier origin revision finishes
  after the origin was replaced
- **THEN** the system discards the stale result and does not expose it as the
  current portrait

### Requirement: Legacy presets normalize without rewriting played games
The system SHALL synthesize a story origin for legacy presets and SHALL leave
played game timelines and histories unchanged.

#### Scenario: Legacy preset has no exact date
- **WHEN** a preset contains era year 1899 and starting age 25 but no start date
- **THEN** its synthesized origin uses 1899-01-01 and starting age 25

#### Scenario: Legacy preset prose conflicts with its exact date
- **WHEN** a preset's authoritative date year differs from an explicit year in
  its era narrative
- **THEN** the preset is marked for origin review and cannot start until the
  origin is regenerated

