## MODIFIED Requirements

### Requirement: Current story media matches the visible story phase
The gameplay page SHALL avoid showing media from an older story phase while
media for the currently visible completed story phase is being fetched or
generated.

#### Scenario: Result illustration is still loading
- **GIVEN** the result or summary story phase is visible
- **AND** an event-stage illustration from the previous choice prompt is already present
- **AND** the result-stage illustration request is still loading or generating
- **WHEN** the scene illustration area renders
- **THEN** it MUST show a result illustration loading state
- **AND** it MUST NOT show the stale event-stage illustration as the primary current scene

#### Scenario: Result illustration is unavailable after loading finishes
- **GIVEN** the result or summary story phase is visible
- **AND** no result-stage illustration is available
- **AND** no result-stage illustration request is loading
- **WHEN** an event-stage illustration is available
- **THEN** the page MAY fall back to the event-stage illustration.
