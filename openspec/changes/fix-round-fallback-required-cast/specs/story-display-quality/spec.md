## ADDED Requirements

### Requirement: Round fallback preserves preset key people

When round-event generation falls back after validation failures, the fallback story SHALL still preserve the player's preset relationship network.

#### Scenario: AI output repeatedly drifts away from required cast

- **GIVEN** character settings define preset key people such as a mentor, close
  friend, or peer
- **AND** the generated round story fails quick validation after retry because it
  omits those people or drifts into another setting
- **WHEN** the system builds the fallback round story
- **THEN** the fallback story MUST include at least one canonical preset key
  person
- **AND** it MUST NOT reuse the rejected drifted story text
