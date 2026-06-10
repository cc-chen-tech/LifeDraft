## ADDED Requirements

### Requirement: Choice Complete Payload Feeds Auto Reading

After a player choice completes, the frontend SHALL expose the completed choice
story to the story voice reading target even when the SSE stream did not emit
separate story chunks.

#### Scenario: Choice SSE has only complete event text

- **GIVEN** the player selects an option from the current story
- **AND** the `/choice` SSE response sends `complete.event_description` without
  prior `story` chunks
- **WHEN** the frontend enters the result phase
- **THEN** the current story text MUST include the complete event description
- **AND** the unified sound console MUST receive that text as the current-story
  auto-read target
- **AND** streamed paths that already wrote the same text MUST NOT duplicate it.
