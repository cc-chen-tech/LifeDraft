## ADDED Requirements

### Requirement: Every quality level has one execution budget
Story generation MUST resolve the selected quality level to a typed budget that controls prompt length, provider tokens, retry behavior, AI consistency, and progress expectation.

#### Scenario: Fast budget
- **WHEN** quality level is `fast`
- **THEN** target length SHALL be 350-600 Chinese characters
- **AND** provider output SHALL be capped at 2,048 tokens
- **AND** quick-validation regeneration and AI consistency SHALL be disabled

#### Scenario: Higher-quality budgets
- **WHEN** quality level is `expert` or `master`
- **THEN** its longer target and validation policy SHALL remain distinct from fast

### Requirement: Round prompts receive the real quality level
The round-event prompt producer MUST receive the story generator's selected quality level.

#### Scenario: Fast round prompt
- **WHEN** a fast generator builds a round prompt
- **THEN** the prompt SHALL state the fast length target
- **AND** it SHALL NOT contain the 1,500-2,000-character master target

### Requirement: Fast uses one story provider call
Fast mode MUST NOT make a second story-generation provider call for quick-validation repair or AI consistency repair.

#### Scenario: Local quick validation reports an issue
- **WHEN** the first fast story has a local validation issue
- **THEN** the issue SHALL be recorded as a diagnostic
- **AND** generation SHALL continue without a second story provider call

#### Scenario: World model exists
- **WHEN** fast generation has a world model
- **THEN** AI consistency validation SHALL be skipped

### Requirement: Fast progress is visible
The existing generation progress surface SHALL show the selected fast stage, actual elapsed time, and its bounded expected duration.

#### Scenario: Browser watches fast generation
- **WHEN** the no-mock E2E browser selects fast generation and enters a busy phase
- **THEN** the visible progress SHALL identify fast mode
- **AND** it SHALL show the expectation derived from the production budget

### Requirement: Real persistence and all gates are verified
The selected fast quality level SHALL survive the real database save-read chain, and all required tests SHALL be registered in `test.sh` without mocks or skips.

#### Scenario: Saved fast game
- **WHEN** a fast game is saved and loaded
- **THEN** its constraint level SHALL remain `fast`

#### Scenario: Full verification
- **WHEN** test layers run with `.env`
- **THEN** static, import, contract, DB, and browser budget tests SHALL execute
