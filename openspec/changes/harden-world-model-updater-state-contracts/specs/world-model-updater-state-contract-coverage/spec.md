## ADDED Requirements

### Requirement: World model update transitions are maintained
Maintained backend contracts SHALL verify concrete location, career, commitment, and causal state transitions without mocks or external dependencies.

#### Scenario: Updates resolve and age out
- **WHEN** pending commitments or causal chains are resolved beyond their retention window
- **THEN** updater state MUST remove them while retaining active records
