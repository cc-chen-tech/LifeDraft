## ADDED Requirements

### Requirement: Weekly finalization core is deterministic
The maintained suite SHALL verify empty-week and provider-failure summaries,
story compression delegation, round information, and weekly mood decay without
threads or network calls.

#### Scenario: Weekly summary cannot be generated
- **WHEN** the finalizer has no rounds or its local summary collaborator raises
- **THEN** it returns the language-appropriate fallback with no bonus effects.

#### Scenario: Current round is inspected
- **WHEN** the finalizer receives a concrete player state
- **THEN** it reports current week, round, completion count, and last-round
  status from that state.

### Requirement: Periodic summary bookkeeping preserves history
The maintained suite SHALL verify four-week and yearly summaries are appended
only when sufficient history exists.

#### Scenario: Four weekly summaries are available
- **WHEN** a state contains four recent weekly summaries
- **THEN** a combined four-week entry is recorded.

#### Scenario: Twelve four-week summaries are available
- **WHEN** a state contains twelve recent four-week summaries
- **THEN** a yearly entry is recorded with the calculated year.

### Requirement: Maintained workflow parity includes finalizer contracts
Both ordered backend workflow lists SHALL include the finalizer state contract
once at the same position.

#### Scenario: Workflow list comparison
- **WHEN** maintained workflow paths are parsed
- **THEN** both ordered lists are equal and include the finalizer suite once.
