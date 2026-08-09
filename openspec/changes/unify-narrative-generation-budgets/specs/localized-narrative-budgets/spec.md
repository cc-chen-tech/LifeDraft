## ADDED Requirements

### Requirement: Narrative budgets separate product and technical limits
The system SHALL resolve immutable narrative budgets that model localized product target bands, compression thresholds, a 32,000 Unicode-character absolute ceiling, model output-token ceilings, provider-call allowances, and total deadlines as separate fields.

#### Scenario: Resolve quality round defaults
- **WHEN** a round generation budget is resolved for fast, expert, or master quality
- **THEN** Chinese target bands SHALL respectively be 400-700, 800-1400, and 1200-2200 characters
- **AND** compression thresholds SHALL respectively be 1400, 2400, and 4000 characters
- **AND** output-token ceilings SHALL respectively be 1024, 2048, and 4096
- **AND** deadlines SHALL respectively be 60, 120, and 240 seconds.

#### Scenario: Resolve opening and continuation defaults
- **WHEN** an opening or continuation budget is resolved
- **THEN** opening SHALL target 300-500 Chinese characters or 200-350 English words with 1024 output tokens
- **AND** continuation SHALL target 400-700 Chinese characters or 250-450 English words with 1536 output tokens
- **AND** each SHALL use its documented localized compression threshold.

### Requirement: Length measurement follows localized units
The system SHALL measure Chinese product length in Unicode code points excluding whitespace, English product length in words, and the absolute technical ceiling in raw Unicode code points.

#### Scenario: Measure Chinese and English independently
- **WHEN** equivalent Chinese and English narratives are measured
- **THEN** the Chinese result SHALL use the `characters` unit
- **AND** the English result SHALL use the `words` unit
- **AND** neither result SHALL be substituted with provider-token estimates.

### Requirement: Rewrite and regeneration inherit request context
The system SHALL derive rewrite targets from the submitted story and SHALL resolve regeneration from the current narrative kind and quality budget.

#### Scenario: Rewrite a complete story
- **WHEN** a rewrite operation is resolved with an original measured length
- **THEN** its soft target SHALL be 80%-120% of that length
- **AND** its target maximum SHALL NOT exceed the scenario compression threshold
- **AND** its output tokens, call allowances, and deadline SHALL remain those of the originating request.

#### Scenario: Regenerate at active quality
- **WHEN** a story is regenerated at fast, expert, or master quality
- **THEN** the resolver SHALL use the current quality budget rather than a fixed rewrite or Harness token value.

### Requirement: Prompt lengths come from resolved budgets
All active narrative prompts SHALL format numeric length requirements from a resolved budget, and style manifests SHALL NOT override them with numeric chapter lengths.

#### Scenario: Static critical-path gate
- **WHEN** narrative prompt, style, and provider call sites are scanned
- **THEN** opening, round, continuation, rewrite, regeneration, consistency repair, and truncation recovery SHALL contain no unbudgeted fixed 4096 or 8192 output-token argument
- **AND** active style constraints SHALL contain no numeric chapter-length range.
