## ADDED Requirements

### Requirement: Historical summary relevance uses real gameplay state
The maintained backend contracts SHALL execute deterministic historical-summary
selection against concrete `PlayerState` data without mocked gameplay state or
random sources.

#### Scenario: Multiple state sources identify a relevant summary
- **WHEN** a prior summary mentions a pending commitment, an active
  foreshadowing character, or a previously seen configured character
- **THEN** relevance selection MUST return that eligible historical summary

#### Scenario: Current and future summaries are ineligible
- **WHEN** a matching weekly or yearly summary belongs to the current or a
  future week
- **THEN** relevance selection MUST not return that summary

### Requirement: Scene character contracts remain provider-free
The maintained backend contracts SHALL execute the multi-character scene helper
suite without a database, image provider, network request, mock, or timing
dependency.

#### Scenario: Character manifest contains distinct positioned characters
- **WHEN** a story includes configured player, relationship, and family
  characters
- **THEN** the scene helpers MUST include each applicable character once with
  the required position and distinction constraints
