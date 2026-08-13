## ADDED Requirements

### Requirement: Maintained gates cover grounded life summaries
The maintained backend workflows SHALL include deterministic contracts ensuring life summaries use the requested story range, preserve uncertainty, reject unsupported facts, and build grounded fallbacks from real stored history.

#### Scenario: Unsafe summary content
- **WHEN** a provider summary introduces unsupported resolution, identity, or resource claims
- **THEN** the maintained backend gate MUST fail if a grounded fallback is not used

#### Scenario: Saved history read
- **WHEN** four weeks of story history are saved and read back through the database
- **THEN** the maintained backend gate MUST fail if the grounded summary loses source evidence
