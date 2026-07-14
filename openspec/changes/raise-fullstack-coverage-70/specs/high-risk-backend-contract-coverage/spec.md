## ADDED Requirements

### Requirement: High-risk backend contracts are covered deterministically
The repository SHALL add focused tests for uncovered high-risk backend state,
response-shape, fallback, and persistence behavior without external provider
or network dependencies.

#### Scenario: A high-risk state contract is exercised
- **WHEN** a test covers gameplay, collection, world-model, image, or
  illustration behavior selected for this change
- **THEN** it MUST assert observable output or persisted state for a boundary
  condition rather than only collaborator call counts

### Requirement: Promoted backend tests are workflow-parity safe
Any backend test added to the maintained coverage selection SHALL be added to
the maintained backend-test selection in the same change and SHALL pass twice
without skips, xfails, provider calls, network calls, or timing dependencies.

#### Scenario: Stable candidate promotion
- **WHEN** a candidate backend suite passes twice in the maintained workflow
  environment
- **THEN** both maintained workflow selections MUST include the same suite

#### Scenario: Unstable candidate rejection
- **WHEN** a candidate suite skips, xfails, invokes a provider or network, or
  fails on either validation run
- **THEN** neither maintained workflow selection MUST include that suite
