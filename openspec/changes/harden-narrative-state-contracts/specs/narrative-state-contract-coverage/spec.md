## ADDED Requirements

### Requirement: Narrative state transitions preserve bounded valid context
Maintained backend contracts SHALL exercise deterministic narrative state updates against concrete `PlayerState` data without mocks, provider calls, databases, random patches, or timing dependencies.

#### Scenario: Storyline and fact updates replace obsolete context
- **WHEN** storyline and fact updates add, resolve, replace, or expire entries
- **THEN** the resulting player state MUST retain only current, bounded context

#### Scenario: Seed and habit updates normalize and bound history
- **WHEN** foreshadowing and habit updates contain invalid metadata, duplicate
  values, expired entries, or more than their per-domain limit
- **THEN** the resulting player state MUST retain valid normalized entries in
  the documented priority order
