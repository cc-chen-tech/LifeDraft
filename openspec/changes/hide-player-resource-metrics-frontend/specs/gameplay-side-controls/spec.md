## ADDED Requirements

### Requirement: Runtime gameplay controls hide resource metrics
Gameplay runtime controls SHALL NOT display the raw player resource metric labels or numeric values for energy, mood, knowledge, or wealth.

#### Scenario: Gameplay status bar renders without resource metrics
- **WHEN** the play page renders a status bar with player state containing `energy`, `mood`, `knowledge`, and `wealth`
- **THEN** the status bar MUST continue to display age/week/progress context
- **AND** the status bar MUST NOT display `精力`, `情绪`, `学识`, `财富`, `energy`, `mood`, `knowledge`, or `wealth` as runtime metrics

#### Scenario: Resource-only choice effects are hidden
- **WHEN** a choice only changes `energy`, `mood`, `knowledge`, or `wealth`
- **THEN** the choice impact surface MUST render no visible metric card for those changes

#### Scenario: Non-resource choice effects can remain visible
- **WHEN** a choice impact includes non-resource effects
- **THEN** the choice impact surface MAY render those non-resource effects without reintroducing hidden resource metrics
