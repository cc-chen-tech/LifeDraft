## ADDED Requirements

### Requirement: Retained authoritative evidence is serializable
The maintained backend suite SHALL verify that assistant evidence retains
authoritative wealth records when verbose settings reach the evidence limit and
that optional evidence metadata is serialized only when present.

#### Scenario: Settings reach the evidence limit
- **WHEN** a player state contains more setting scalars than the evidence cap
- **THEN** the evidence includes the current authoritative wealth balance and
  excludes at least one disposable setting record.

#### Scenario: Optional record fields are absent
- **WHEN** an evidence record has no source event, effective time, or metadata
- **THEN** its serialized dictionary contains only kind, subject, and fact.

### Requirement: Assistant answers remain evidence-bound
The maintained backend suite SHALL verify accepted and rejected deterministic
assistant payloads without mocks or network access.

#### Scenario: Valid cited answer
- **WHEN** a provider returns a factual answer with a retained evidence ID and
  overlapping fact text
- **THEN** the service returns a certain answer with that citation.

#### Scenario: Invalid payload is rejected
- **WHEN** a provider returns malformed payloads, unsupported concrete values,
  or uncited factual text through all attempts
- **THEN** the service returns the language-appropriate uncertain fallback.

#### Scenario: Unknown English person is queried
- **WHEN** an English query names a person outside the authoritative records
- **THEN** the service returns uncertainty without requiring a model response.

### Requirement: Maintained workflow parity includes grounding contracts
Both backend workflow test lists SHALL include the grounding evidence contract
in the same order.

#### Scenario: Workflow list comparison
- **WHEN** the coverage and backend test workflows are parsed into ordered test
  paths
- **THEN** the grounding evidence contract occurs once in both lists at the
  same position.
