## ADDED Requirements

### Requirement: Harness continuity rules have deterministic contracts
Maintained backend contracts SHALL cover temporal, causal, and information-boundary validators through public APIs using concrete local inputs without mocks, skips, provider calls, databases, randomness, or timing dependencies.

#### Scenario: Temporal state conflicts with narrative text
- **WHEN** story text contradicts the current season or a known player age
- **THEN** the temporal validator MUST return a failed result with structured consistency details

#### Scenario: Causal consequence becomes overdue or contradictory
- **WHEN** a pending causal chain is overdue without an expressed consequence or its expected consequence is contradicted
- **THEN** the causal validator MUST return a failed result that identifies the causal issue

#### Scenario: Character reveals inaccessible information
- **WHEN** a character's speech or knowledge claim includes a configured unknown secret
- **THEN** the information-barrier validator MUST return a failed result identifying that secret

#### Scenario: Configured knowledge is accessible
- **WHEN** a character's claim is supported by configured knowledge and no unknown secret is exposed
- **THEN** the information-barrier validator MUST return a passing result
