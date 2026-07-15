## ADDED Requirements

### Requirement: Story fallback preserves established Chinese context
The maintained backend suite SHALL verify that Chinese story fallbacks include
the established era, trait, player identity, and anchored relationship where
those fields are available.

#### Scenario: Contextual Chinese fallback
- **WHEN** a Chinese fallback is built from a player state with an era, trait,
  and required relationship person
- **THEN** it includes those grounding details and only offers a small next
  decision

### Requirement: Story fallback has stable English and invalid-round behavior
The maintained backend suite SHALL verify that English fallbacks retain the
anchored relationship and use the generic day label for an invalid round index.

#### Scenario: English fallback with invalid round number
- **WHEN** an English fallback is built for a round number outside the weekly
  range
- **THEN** it uses the generic day label and preserves the relationship anchor
