## ADDED Requirements

### Requirement: Character creation uses one story-origin step
The character creator SHALL present story origin, gender, world, and portrait as
the four manual steps and SHALL NOT present independent era, age, birth-year, or
start-date controls.

#### Scenario: Player enters character creation
- **WHEN** the creation page loads for a new character
- **THEN** the first generated step is `故事起点`, the total manual step count is
  four, and no editable date, separate age step, or birth year is shown

### Requirement: Origin replacement invalidates dependent settings
Accepting a replacement story origin SHALL preserve identity and gender while
invalidating world, portrait, family, relationships, traits, and matched
narrative style derived from the previous origin.

#### Scenario: Historical origin changes to a modern origin
- **WHEN** a player accepts feedback changing a 960/age-20 origin to a
  2026/age-28 origin
- **THEN** the creator returns to world generation and none of the historical
  world, portrait, family, relationship, trait, or style results remain active

### Requirement: Downstream generation consumes the canonical origin
World, family, relationship, portrait, and story generation SHALL use
`story_origin` before compatibility era or age fields.

#### Scenario: Compatibility fields disagree with origin
- **WHEN** a generation request contains a canonical 2026/age-28 origin and stale
  compatibility era or age values
- **THEN** the generated context uses 2026 and age 28

### Requirement: Completion review displays the story origin
The completed character view SHALL always show the accepted story origin and
route origin modification through whole-card feedback regeneration.

#### Scenario: Character generation completes
- **WHEN** all background settings are ready
- **THEN** the completion view shows the exact start date, starting age, and
  origin context without a birth year
