## ADDED Requirements

### Requirement: Round fallback preserves preset key people

Round-event generation fallback stories SHALL preserve the player's preset relationship network and role context after validation failures or model exceptions.

#### Scenario: AI output repeatedly drifts away from required cast

- **GIVEN** character settings define preset key people such as a mentor, close
  friend, or peer
- **AND** the generated round story fails quick validation after retry because it
  omits those people or drifts into another setting
- **WHEN** the system builds the fallback round story
- **THEN** the fallback story MUST include at least one canonical preset key
  person
- **AND** it MUST NOT reuse the rejected drifted story text

#### Scenario: Round service fallback after model exception

- **GIVEN** character settings define a modern occupation and preset key people
- **WHEN** the model raises before returning a round event
- **THEN** the service-level fallback story MUST include at least one canonical
  preset key person
- **AND** it MUST preserve the character's role or occupation context
- **AND** it MUST NOT return a generic fallback unrelated to the player's setup
