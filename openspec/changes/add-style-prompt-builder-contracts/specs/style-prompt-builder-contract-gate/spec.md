## ADDED Requirements

### Requirement: Style manifests produce layered generation guidance
The maintained backend gate SHALL verify that a populated style manifest emits
hard constraints, soft guidance, and global temperature information.

#### Scenario: Full manifest is rendered
- **WHEN** a manifest supplies philosophy, structure, technique, language, and
  global parameter values
- **THEN** the rendered prompt SHALL include the corresponding hard and soft
  markers and supplied values

### Requirement: Optional style guidance remains deterministic
The maintained backend gate SHALL verify no-style fallback, sparse chapter
guidance, scheduled temperature lookup, and prompt budget truncation.

#### Scenario: Chapter and temperature guidance is available
- **WHEN** a manifest supplies chapter rules and a temperature schedule
- **THEN** the builder SHALL return their guidance and scene-specific
  temperature while falling back to the base temperature for other scenes

#### Scenario: Prompt budget truncates assembled guidance
- **WHEN** a populated manifest is rendered with a positive small token budget
- **THEN** the returned guidance SHALL not exceed twice that token count in
  characters
