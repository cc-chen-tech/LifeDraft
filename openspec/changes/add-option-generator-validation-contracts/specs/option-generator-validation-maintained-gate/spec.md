## ADDED Requirements

### Requirement: Option fallback and validation are maintained
The maintained backend workflows SHALL execute provider-free option fallback and validation contracts.

#### Scenario: Interrupted option generation regression
- **WHEN** an option generation round falls back or normalizes relationship effects
- **THEN** it preserves context-specific choices, canonical relationships, and actionable effect defaults.
