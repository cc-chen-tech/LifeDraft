## ADDED Requirements

### Requirement: Failed choice generation is atomic
The system SHALL not commit effects, wealth transactions, historical records, or round
advancement until a selected standard or custom choice has a valid continuation.

#### Scenario: Continuation provider fails after a choice is selected
- **WHEN** continuation generation fails or returns invalid narrative text
- **THEN** the system MUST return a retryable generation error
- **AND** the current event, player resources, wealth ledger, history, and round index
  MUST remain unchanged.

#### Scenario: Custom choice effects cannot be evaluated
- **WHEN** custom-choice effect evaluation fails or returns invalid effect data
- **THEN** the system MUST return a retryable generation error
- **AND** it MUST NOT substitute generic effects or a generic continuation.

### Requirement: Repeated fallback decision sets are not playable
The system SHALL not turn a failed option-generation attempt into a decision set that
duplicates recent committed choices.

#### Scenario: Contextual fallback repeats a recent choice set
- **WHEN** fallback options normalize to the same decision texts as recent committed
  rounds
- **THEN** the system MUST surface a retryable option-generation error
- **AND** it MUST preserve the valid story instead of committing or displaying the
  repeated choice set.
