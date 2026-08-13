## ADDED Requirements

### Requirement: Invalid world-model updates preserve valid state
The maintained backend suite SHALL verify that incomplete location, career,
commitment, and causal update payloads do not create partial world-model data.

#### Scenario: Required field is omitted
- **WHEN** a real PlayerState receives an update missing its required identity
  or content field
- **THEN** its corresponding world-model collection MUST remain unchanged.

### Requirement: Character synchronization preserves preset relationships
The maintained backend suite SHALL verify that an AI-introduced name is not
added when its inferred story role conflicts with an existing preset role.

#### Scenario: Substitute role appears in story
- **WHEN** relationship effects contain a new name described near a protected
  preset role in the story
- **THEN** character settings and the relationship map MUST not add that name.

### Requirement: Scheduled-event cleanup is deterministic
The maintained backend suite SHALL verify that null player state is a no-op
and only stale terminal events are removed from a real PlayerState.

#### Scenario: Mixed event lifecycle cleanup
- **WHEN** scheduled events include a pending event and terminal events on
  opposite sides of the retention boundary
- **THEN** cleanup MUST remove only the stale terminal event and return its
  count.
