## ADDED Requirements

### Requirement: Life summaries use the exact selected timeline
The life-summary service MUST derive and state the exact inclusive week range represented by the selected story history.

#### Scenario: Four weeks of history
- **WHEN** selected history spans internal weeks 0 through 3
- **THEN** the summary context SHALL identify `第1-4周`
- **AND** generated text describing the period as half a year or longer SHALL be rejected

### Requirement: Summary claims remain grounded in story evidence
The provider prompt and output boundary MUST restrict factual claims to supplied round-history text and choices.

#### Scenario: Conflicting source claims
- **WHEN** story evidence contains conflicting registration, tender, illness, or identity claims
- **THEN** the prompt SHALL require the conflict to remain unresolved
- **AND** the summary SHALL NOT merge the alternatives into one certain fact

#### Scenario: Unsupported number
- **WHEN** generated summary text introduces a numeric claim absent from the source history
- **THEN** the generated text SHALL be rejected in favor of the grounded fallback

### Requirement: Summary does not endorse legal evasion
The life summary MUST NOT characterize evasion of contractual, regulatory, or legal duties as compliant or lawful.

#### Scenario: Non-compete workaround
- **WHEN** story text describes using a relative's name to avoid a non-compete restriction
- **THEN** the summary SHALL describe it neutrally as a disputed or risky action
- **AND** it SHALL NOT call it a compliant path

### Requirement: Removed resource metrics stay out of summaries
Energy, mood, knowledge, and wealth values SHALL NOT be injected into the summary prompt, deterministic fallback, or returned summary.

#### Scenario: Player has mutable metrics
- **WHEN** the player state contains energy, mood, knowledge, and wealth
- **THEN** none of those labels or values SHALL appear merely because they exist in player state

### Requirement: Grounding survives real persistence and browser display
The no-mock verification path MUST load round history from a real database and show the grounded result in the real summary panel.

#### Scenario: Saved four-week story
- **WHEN** four weeks of story history are saved and loaded
- **THEN** summary construction SHALL preserve the exact range and source excerpts

#### Scenario: Browser summary panel
- **WHEN** the E2E browser opens a grounded life summary
- **THEN** the panel SHALL show `第1-4周`
- **AND** it SHALL not show removed resource metrics or a half-year claim

### Requirement: Repository gates execute the coverage
The new static, import, contract, real DB, and browser tests MUST be registered in `test.sh` without mocks or skips.

#### Scenario: Full local verification
- **WHEN** the repository test layers run with `.env`
- **THEN** all life-summary grounding coverage SHALL execute
