## ADDED Requirements

### Requirement: Legacy contract groups are restored incrementally
Legacy backend failure groups SHALL be repaired in coherent batches and verified with targeted pytest runs before any maintained-gate promotion.

#### Scenario: Same-root-cause failures are fixed together
- **WHEN** multiple legacy tests fail because a current production helper lost a compatibility entry point
- **THEN** the implementation MUST restore the behavior through the current helper path or the tests MUST be updated to the current public contract

#### Scenario: Stale internals are not blindly restored
- **WHEN** a legacy test asserts removed private state that conflicts with current product behavior
- **THEN** the failure MUST remain triaged until a current product requirement justifies restoring that state

### Requirement: Chinese text normalization remains available
Chinese generated story text SHALL normalize obvious English punctuation artifacts before display or persistence, and the legacy StoryGenerator compatibility entry point SHALL delegate to the current text-quality helper.

#### Scenario: Chinese punctuation is normalized
- **WHEN** Chinese text contains English punctuation, brackets, quotes, or dotted pauses
- **THEN** normalization MUST return Chinese punctuation while preserving already-normalized Chinese punctuation

#### Scenario: Non-Chinese text is not altered
- **WHEN** normalization runs for English language text
- **THEN** it MUST return the original text unchanged
