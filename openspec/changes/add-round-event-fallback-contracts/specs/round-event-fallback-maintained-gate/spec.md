## ADDED Requirements

### Requirement: Round-event fallback is maintained
The maintained backend workflows SHALL execute provider-free scheduled-event fallback contracts.

#### Scenario: Scheduled generation failure
- **WHEN** scheduled event generation falls back
- **THEN** all commitment descriptions and actionable bilingual options remain available.
