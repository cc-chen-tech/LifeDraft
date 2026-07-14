## ADDED Requirements

### Requirement: World-model constraint matrix is maintained
The maintained backend workflows SHALL execute deterministic world-model constraint rendering contracts.

#### Scenario: Persisted state prompt regression
- **WHEN** a story prompt is assembled from populated world state
- **THEN** both language renderers retain supported state categories and exclude resolved causal chains.
