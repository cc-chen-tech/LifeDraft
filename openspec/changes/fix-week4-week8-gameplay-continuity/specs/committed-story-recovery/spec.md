## ADDED Requirements

### Requirement: Legacy saves reconstruct committed-story evidence
The system SHALL reconstruct an authoritative timeline from durable historical round
records when a restored save has no committed continuity timeline.

#### Scenario: Legacy save has completed rounds and an empty ledger
- **WHEN** a restored player state contains ordered `round_history` records but its
  continuity ledger has no timeline
- **THEN** the system MUST persist one idempotent committed timeline entry per completed
  round before generating the next event
- **AND** each entry MUST retain the historical summary, selected choice, date, and
  story source hash.

#### Scenario: Existing ledger is already authoritative
- **WHEN** a restored player state contains a non-empty committed continuity timeline
- **THEN** the system MUST NOT duplicate or rewrite its historical entries.

### Requirement: Prompt context retains exact committed choices
The system SHALL render exact committed choices in continuity constraints alongside
their compressed summaries.

#### Scenario: Player completed a concrete custom action
- **WHEN** a historical choice records a concrete completed action
- **THEN** the next event prompt MUST include that action as committed evidence
- **AND** it MUST NOT present the same action as merely unstarted planning.
