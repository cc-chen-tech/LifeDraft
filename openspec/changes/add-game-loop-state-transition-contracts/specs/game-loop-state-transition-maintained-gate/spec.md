## ADDED Requirements

### Requirement: Game loop state transitions are maintained
The maintained backend workflows SHALL execute deterministic weekly decay and event cleanup contracts.

#### Scenario: Week transition regression
- **WHEN** a week transition fails to decay low resources or clear persisted event state
- **THEN** both maintained workflows fail before release.
