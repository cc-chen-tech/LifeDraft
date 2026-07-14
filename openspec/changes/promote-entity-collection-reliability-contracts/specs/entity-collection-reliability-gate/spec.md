## ADDED Requirements

### Requirement: Entity collection reliability contracts run in maintained tests
The maintained test suite SHALL execute deterministic entity collection
reliability contracts for story people, false-positive filtering, context
selection, and add-response consumer behavior.

#### Scenario: Maintained entity collection run
- **WHEN** the maintained backend workflow runs
- **THEN** it MUST execute the entity collection reliability contract file
