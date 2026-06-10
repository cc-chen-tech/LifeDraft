## ADDED Requirements

### Requirement: Custom choice JSON results preserve preset persona authority

Custom-choice JSON result generation SHALL enforce the same preset key-person and world-boundary authority used by ordinary story continuations.

#### Scenario: Custom choice prompt includes persona authority

- **WHEN** the system builds a custom-choice result prompt for a game with preset key people
- **THEN** the prompt MUST include the canonical key people, their roles, and rules forbidding rename or replacement
- **AND** the prompt MUST include realistic world-boundary constraints when the character settings describe a realistic modern world.

#### Scenario: Drifted custom choice result is retried

- **WHEN** the model returns a JSON custom-choice result whose `story_continuation` replaces preset key people with a new named role substitute
- **THEN** the backend MUST reject that result
- **AND** it MUST retry generation with the validation failure included before returning a result.
