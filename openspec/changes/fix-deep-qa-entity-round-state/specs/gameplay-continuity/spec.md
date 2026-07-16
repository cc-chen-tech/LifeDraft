## ADDED Requirements

### Requirement: Current round display uses player-facing numbering
Gameplay SHALL preserve zero-based `round_number` in state while rendering the active scene-image round label as one-based for players.

#### Scenario: First round of a week
- **WHEN** a scene image reports `round_number` as `0`
- **THEN** its visible label MUST render `第 1 轮` and MUST NOT render `第 0 轮`

#### Scenario: Subsequent round
- **WHEN** a scene image reports `round_number` as `1`
- **THEN** its visible label MUST render `第 2 轮`
