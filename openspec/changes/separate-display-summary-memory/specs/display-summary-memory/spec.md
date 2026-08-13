## ADDED Requirements

### Requirement: Localized display summaries use one budget contract

The system SHALL resolve week, month, year, and life display-summary targets from one localized budget contract. Chinese SHALL be measured as Unicode characters and English SHALL be measured as words.

#### Scenario: Chinese and English targets remain distinct

- **WHEN** the same summary kind is requested in Chinese and English
- **THEN** the prompt and validation SHALL use the localized target band and unit

### Requirement: Display compaction preserves complete sentences

The system SHALL compact display prose only at complete sentence boundaries and SHALL NOT store a raw character-sliced fragment as a summary.

#### Scenario: Oversized provider summary is compacted

- **WHEN** a provider returns display prose above its compression threshold
- **THEN** the stored result SHALL contain only complete sentences and end with valid sentence punctuation

### Requirement: Structured memory remains authoritative and independently durable

The system SHALL treat `ContinuityLedger` facts, relationships, commitments, timeline entries, and source event IDs as model authority. Display-summary generation failure SHALL NOT undo a committed event or its deterministic ledger data.

#### Scenario: Display summary fails after event commit

- **WHEN** an event, choice, and effects have been committed and display-summary generation fails
- **THEN** the ledger SHALL still retain the source event, choice, effects, and all pre-existing authoritative facts

### Requirement: Legacy summary generators are compatibility wrappers

The system SHALL retain the public weekly, monthly, and yearly summary-generator interfaces for one compatibility release while delegating prose generation and normalization to the shared summary generator.

#### Scenario: Existing caller invokes a legacy generator

- **WHEN** an existing caller invokes a legacy weekly, monthly, or yearly generator
- **THEN** it SHALL receive the same public result shape and shared localized summary behavior
