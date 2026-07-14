## ADDED Requirements

### Requirement: Maintained gate validates narrative fate echoes
The maintained backend selection SHALL validate proposition registration, trigger evaluation, expiry cleanup, and cross-volume echoes.

#### Scenario: Proposition trigger is evaluated
- **WHEN** a registered narrative proposition reaches its configured trigger conditions
- **THEN** the maintained contract MUST require the corresponding echo to be emitted
