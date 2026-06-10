## ADDED Requirements

### Requirement: Preset relationship networks remain authoritative

Story generation prompts and fast validation SHALL prevent newly invented named
relationship networks from taking over a story that has an explicit preset cast.

#### Scenario: Multi-person conflict uses too little preset cast

- **GIVEN** character settings define at least three preset key people
- **AND** generated story text mentions multiple newly named outside characters
- **WHEN** fewer than 80% of the preset key people appear in that generated story
- **THEN** quick validation SHALL reject the story before options are generated
- **AND** the retry instruction SHALL ask the model to rewrite around the preset relationship network.

#### Scenario: Focused scenes without replacement cast remain valid

- **GIVEN** character settings define preset key people
- **WHEN** a focused scene uses one relevant preset person and does not introduce a competing named cast
- **THEN** validation SHALL allow the scene to continue.
