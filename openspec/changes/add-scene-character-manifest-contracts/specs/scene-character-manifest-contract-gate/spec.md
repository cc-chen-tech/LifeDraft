## ADDED Requirements

### Requirement: Scene character roster reflects story evidence
The maintained backend gate SHALL verify that the player and mentioned known
people appear once in scene preparation, while unmentioned people do not.

#### Scenario: Mentioned family and relationship characters are included
- **WHEN** story text mentions configured family and relationship characters
- **THEN** the roster SHALL include them with descriptions and no duplicates

### Requirement: Scene prompt data remains compatible
The maintained backend gate SHALL verify structured and legacy character fields
produce bounded era, age, gender, appearance, and multi-person layout text.

#### Scenario: Structured settings form a multi-person manifest
- **WHEN** the service receives structured era and appearance settings
- **THEN** it SHALL produce bounded character info and distinct layout entries
