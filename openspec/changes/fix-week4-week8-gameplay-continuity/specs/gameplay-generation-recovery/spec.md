## ADDED Requirements

### Requirement: Life-summary generation has a bounded outcome
The system SHALL bound provider and browser waits for a life-summary request and keep
the playable game state responsive.

#### Scenario: Summary provider exceeds the server deadline
- **WHEN** the provider does not finish within the configured summary deadline
- **THEN** the API MUST return an evidence-only deterministic summary result
- **AND** it MUST NOT mutate the current event, round, or player state.

#### Scenario: Browser summary request exceeds its client deadline
- **WHEN** the browser does not receive a life-summary response before its deadline
- **THEN** the loading indicator MUST clear and a retryable error MUST be visible
- **AND** existing story controls and recovery controls MUST remain usable without a
  page refresh.
