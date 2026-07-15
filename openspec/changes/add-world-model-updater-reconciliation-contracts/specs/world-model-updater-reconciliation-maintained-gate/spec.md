## ADDED Requirements

### Requirement: World-model update reconciliation is maintained
The maintained backend workflows SHALL execute deterministic world-model reconciliation contracts.

#### Scenario: Persisted analysis update regression
- **WHEN** analysis creates new records or resolves a matching commitment
- **THEN** PlayerState stores current-week defaults and the resolved lifecycle state.
