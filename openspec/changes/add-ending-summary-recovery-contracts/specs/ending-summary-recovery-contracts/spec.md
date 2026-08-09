## ADDED Requirements

### Requirement: Ending summaries have deterministic provider and fallback behavior
The maintained suite SHALL verify that a generated ending receives life context and that a provider failure returns the localized template summary.

#### Scenario: Generating or recovering an ending summary
- **WHEN** the ending evaluator has a successful or failing narrative generator
- **THEN** it returns guarded generated prose or a usable localized fallback
