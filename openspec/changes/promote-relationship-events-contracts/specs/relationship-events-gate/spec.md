## ADDED Requirements

### Requirement: Maintained gate validates relationship event definitions
The maintained backend selection SHALL validate relationship event categories, thresholds, requirements, and era-name normalization.

#### Scenario: Relationship event is resolved for an era
- **WHEN** gameplay resolves a defined relationship event for a supported or unknown era
- **THEN** the maintained contract MUST require the correct era label or modern fallback
