## MODIFIED Requirements

### Requirement: Harness terminal rejection is limited to severe continuity failures

The production Harness SHALL use validation findings for diagnostics, but SHALL
deny a completed story only for critical failures that represent severe continuity
corruption.

#### Scenario: Presentation-only critical finding

- **WHEN** a complete story has only a decision-point, narration-person, meta-style,
  or other non-continuity Harness failure
- **THEN** the story remains available for option generation
- **AND** the finding remains observable as a diagnostic

#### Scenario: Severe continuity finding exhausts retries

- **WHEN** a critical established-fact, fabricated-entity, era, temporal, spatial,
  state, item, commitment, information-barrier, or cause-effect failure remains
  after the allowed attempts
- **THEN** the invalid candidate is not used
- **AND** the generator recovers a prior usable candidate or returns an explicit
  generation failure if none exists
