## ADDED Requirements

### Requirement: NPC profile contradictions are detected deterministically
Maintained backend contracts SHALL validate NPC continuity using concrete local profiles without mocks, providers, databases, random patches, or timing dependencies.

#### Scenario: Story conflicts with a known profile
- **WHEN** story text contradicts a known NPC appearance, boundary, identity, or personality
- **THEN** validation MUST fail with the corresponding structured violation
