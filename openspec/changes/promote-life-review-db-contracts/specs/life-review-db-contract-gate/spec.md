## ADDED Requirements

### Requirement: Life review remains a maintained state contract
The maintained backend gate SHALL verify that a player state and achievements
produce a structured life review with resource curves, labels, and an ending
summary without provider access.

#### Scenario: Ending review is derived from saved gameplay state
- **WHEN** a completed player state is evaluated with achievements
- **THEN** the life review SHALL include its documented structured fields and
  curves aligned to the simulated game week
