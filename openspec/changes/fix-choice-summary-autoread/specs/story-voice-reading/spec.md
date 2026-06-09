## MODIFIED Requirements

### Requirement: Completed story text is eligible for automatic reading
The system SHALL automatically request story reading only after a current story is complete, and it SHALL include all completed choice-result phases that still display the current story.

#### Scenario: Generated event reaches options
- **WHEN** a generated event has finished streaming and options are visible
- **THEN** the current story text MUST be eligible for automatic reading

#### Scenario: Choice result waits for next round confirmation
- **WHEN** a player choice has completed and the result phase is visible
- **THEN** the completed choice continuation MUST be eligible for automatic reading

#### Scenario: Choice result enters weekly summary
- **WHEN** a player choice has completed and the page transitions directly into weekly summary
- **THEN** the completed choice continuation visible before the summary MUST be eligible for automatic reading
- **AND** the reading request MUST use that completed choice continuation as the context text
