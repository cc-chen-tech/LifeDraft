## ADDED Requirements

### Requirement: Choices preserve authoritative state
Maintained backend contracts SHALL apply deterministic choices to real PlayerState data without mocks, providers, databases, random patches, or timing dependencies.

#### Scenario: A choice changes resources and wealth
- **WHEN** a valid option contains resource and integer wealth effects
- **THEN** the resulting player, ledger, and decision history MUST agree

#### Scenario: A choice changes a known relationship
- **WHEN** an option changes an existing character relationship
- **THEN** legacy relationships and character affinity MUST remain synchronized
