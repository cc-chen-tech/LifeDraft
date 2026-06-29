## MODIFIED Requirements

### Requirement: Story streaming retries replace the active attempt

The system SHALL prevent duplicate story display when an event or choice stream
is retried, regenerated, or consistency-corrected.

#### Scenario: Choice complete-only continuation

- **WHEN** a choice stream completes with `story_continuation` or
  `event_description`
- **AND** the visible story does not already contain that completed
  continuation
- **THEN** the frontend MUST append the completed continuation to the visible
  story text

#### Scenario: Choice continuation already streamed

- **WHEN** a choice stream completes with `story_continuation` or
  `event_description`
- **AND** the same completed continuation was already appended from SSE story
  chunks
- **THEN** the frontend MUST NOT append the continuation a second time
