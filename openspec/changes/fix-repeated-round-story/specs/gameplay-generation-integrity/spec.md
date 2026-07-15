## ADDED Requirements

### Requirement: Repeated round prose is not committed as new progress

The system SHALL reject a candidate round story that materially duplicates a committed recent
round, even when it passes formatting and cast validation.

#### Scenario: Provider repeats the previous round verbatim

- **GIVEN** a player has a committed previous round story
- **WHEN** the provider returns that same story for the next round
- **THEN** the generator requests a distinct retry before generating options
- **AND** it does not commit the repeated text as the next round

#### Scenario: Retry remains materially duplicated

- **GIVEN** the first candidate and retry both materially duplicate committed story prose
- **WHEN** the round generation completes
- **THEN** it raises `StoryGenerationFailure`
- **AND** no fabricated fallback event replaces the rejected story
