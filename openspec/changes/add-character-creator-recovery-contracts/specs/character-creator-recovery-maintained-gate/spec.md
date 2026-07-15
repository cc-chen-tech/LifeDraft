## ADDED Requirements

### Requirement: Character creation recovery is maintained
The maintained backend workflows SHALL execute deterministic character-creation response-recovery contracts.

#### Scenario: Invalid generated setup regression
- **WHEN** character setup generation returns conflicting era values, zero or low wealth, an incorrect birth year, or out-of-range attributes
- **THEN** CharacterCreator returns corrected persisted setup values before gameplay begins.
