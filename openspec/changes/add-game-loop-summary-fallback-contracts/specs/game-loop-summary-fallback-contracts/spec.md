## ADDED Requirements

### Requirement: GameLoop fallback event coverage
The maintained backend suite SHALL cover GameLoop's localized fallback-event contract without a provider.

#### Scenario: Fallback event reflects current era and round mode
- **WHEN** a Chinese fallback event is created with an era context or round mode
- **THEN** it provides localized context and two valid choices with the expected resource effects

#### Scenario: English fallback is available without state
- **WHEN** an English GameLoop has no active player state
- **THEN** it still returns a valid localized fallback event

### Requirement: GameLoop summary boundary coverage
The maintained backend suite SHALL cover deterministic GameLoop summary paths with concrete recording collaborators.

#### Scenario: Periodic source history is available
- **WHEN** four-week or yearly summary generation has eligible history
- **THEN** the provider receives the bounded history and the loop stores a correctly bounded summary record

#### Scenario: User summary has no decisions
- **WHEN** a user requests a summary over a period without decisions
- **THEN** the loop returns the localized empty-history result without provider invocation

#### Scenario: User summary has decisions
- **WHEN** the period contains decisions
- **THEN** the configured summary collaborator receives the current state and bounded decision list and its result is returned

### Requirement: Maintained workflow parity
The backend coverage and backend-test workflows SHALL enumerate the GameLoop summary/fallback module identically.

#### Scenario: CI enumerates maintained backend tests
- **WHEN** CI derives each maintained backend test list
- **THEN** the GameLoop summary/fallback module occurs once in the same order in both lists
