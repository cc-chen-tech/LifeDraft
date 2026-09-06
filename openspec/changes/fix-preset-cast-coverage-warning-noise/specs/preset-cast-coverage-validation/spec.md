## ADDED Requirements

### Requirement: Aggregate preset-cast coverage is non-blocking

Quick validation SHALL NOT emit a coverage warning or issue solely because a
generated story uses fewer than 80% of the preset key people. Aggregate
preset-cast coverage SHALL NOT trigger a story-generation retry.

#### Scenario: Seven-person network uses four canonical people

- **GIVEN** character settings define seven preset key people
- **AND** generated story text actively uses four of those people
- **WHEN** no explicit required person is missing and no invented person takes
  over a preset role or main plot
- **THEN** quick validation SHALL return no `CAST_COVERAGE_LOW` finding
- **AND** story generation SHALL not retry solely for cast coverage.

#### Scenario: Seven-person network uses five canonical people

- **GIVEN** character settings define seven preset key people
- **AND** generated story text actively uses five of those people
- **WHEN** no explicit required person is missing and no invented person takes
  over a preset role or main plot
- **THEN** quick validation SHALL allow the story without a coverage finding.

### Requirement: Explicit required cast remains blocking

When a caller supplies `required_people`, quick validation SHALL report a hard
issue for each required person absent from the generated story.

#### Scenario: Explicit participant is missing

- **GIVEN** an event explicitly requires a named preset person
- **WHEN** the generated story does not contain that person
- **THEN** quick validation SHALL return a hard missing-required-person issue.

### Requirement: Invented cast cannot replace preset roles

Quick validation SHALL retain hard protection against a high-confidence
invented named person taking over a preset relationship role or driving the
story in place of the preset cast.

#### Scenario: Invented mentor drives the event

- **GIVEN** character settings define a canonical mentor or relationship role
- **AND** the generated story introduces an invented human character
- **WHEN** that character inherits the preset role or drives the main plot while
  the preset cast is absent or sidelined
- **THEN** quick validation SHALL return a hard cast-takeover issue.

#### Scenario: Place or item token is not a person takeover

- **GIVEN** the generated story contains tokens such as a place, item,
  organization, title, or ordinary noun
- **WHEN** those tokens are not used as an invented human replacement
- **THEN** quick validation SHALL NOT return a cast-takeover issue for them.
