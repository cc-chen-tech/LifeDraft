## ADDED Requirements

### Requirement: Maintained backend coverage enforces a proven floor
The system SHALL enforce a 34 percent full-`src` coverage floor for the
maintained backend selection after two independent measurements meet it.

#### Scenario: Maintained coverage regresses below the floor
- **WHEN** the maintained backend selection covers less than 34 percent of
  `src`
- **THEN** the coverage workflow MUST fail

### Requirement: Stable expansion batch remains workflow symmetric
The system SHALL add every stable test from this backend contract expansion to
the maintained coverage and backend-test workflow selections in the same order.

#### Scenario: A candidate test passes twice
- **WHEN** a new contract suite passes twice in the maintained environment
- **THEN** both maintained workflow selections MUST include that suite

#### Scenario: A candidate is unstable
- **WHEN** a candidate suite fails, skips, xfails, or needs a provider,
  network, or timing dependency
- **THEN** neither maintained workflow selection MUST include that suite
