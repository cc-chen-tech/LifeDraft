## ADDED Requirements

### Requirement: Choice fallback is covered by maintained tests
The maintained choice processor contract file SHALL include the unavailable
player-state normalization scenario.

#### Scenario: Maintained coverage run
- **WHEN** the maintained backend coverage command runs
- **THEN** it MUST execute the unavailable-state contract scenario
