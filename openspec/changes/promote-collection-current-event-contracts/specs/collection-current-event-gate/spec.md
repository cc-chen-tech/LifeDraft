## ADDED Requirements

### Requirement: Maintained gate preserves current-event collection recognition
The maintained backend test selection SHALL verify that recognition history includes the unresolved current event and that eligible characters include relationship and storyline evidence without including the player or organization names.

#### Scenario: Current event contains unresolved people
- **WHEN** collection recognition receives state with an unresolved current event and relationship metadata
- **THEN** the maintained contract MUST include eligible people from those sources and exclude the player and organization names
