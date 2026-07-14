## ADDED Requirements

### Requirement: Story fallback continuation is maintained
The maintained backend workflows SHALL execute deterministic fallback continuation contracts.

#### Scenario: Fallback effect mapping regression
- **WHEN** an AI failure requires a fallback continuation
- **THEN** the fallback retains the selected choice and supported mood, knowledge, and relationship effects.
