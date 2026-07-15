## ADDED Requirements

### Requirement: Weekly finalization ledger coverage
The maintained backend suite SHALL cover RoundFinalizer's synchronous weekly reward and summary-record transition with concrete collaborators.

#### Scenario: Weekly bonus includes wealth
- **WHEN** a generated weekly summary grants resource and wealth bonuses
- **THEN** finalization records a source-linked wealth transaction, updates non-wealth resources, writes the weekly summary, advances the week, and reports enrichment dispatch

#### Scenario: Weekly bonus omits wealth
- **WHEN** a weekly summary includes only non-wealth bonuses
- **THEN** finalization persists the current ledger and applies the declared non-wealth resources

### Requirement: Periodic finalization record coverage
The maintained backend suite SHALL cover periodic summary record thresholds.

#### Scenario: Four-week boundary has sufficient weekly records
- **WHEN** four weekly records are available
- **THEN** finalization appends their combined four-week record

#### Scenario: Year boundary has sufficient four-week records
- **WHEN** twelve four-week records are available
- **THEN** finalization appends a yearly record using the latest twelve records

### Requirement: Maintained workflow parity
The coverage and backend-test workflow lists SHALL enumerate the finalization ledger module identically.

#### Scenario: CI derives maintained backend test lists
- **WHEN** each workflow test list is parsed
- **THEN** the finalization ledger module occurs once in the same order
