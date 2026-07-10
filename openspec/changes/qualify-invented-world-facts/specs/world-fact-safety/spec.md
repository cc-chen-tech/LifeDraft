## ADDED Requirements

### Requirement: World prompts establish a factual boundary
World-setting generation MUST instruct the provider not to present unsupported regulations, certifications, official procedures, economic statistics, or exact process timelines as verified real-world facts.

#### Scenario: User requests concrete compliance constraints
- **WHEN** feedback asks for concrete compliance constraints in a realistic setting
- **THEN** the prompt SHALL allow illustrative story assumptions
- **AND** it SHALL require those assumptions to be visibly distinguished from real legal or economic guidance

### Requirement: High-precision generated claims are qualified before persistence
The production character creator SHALL qualify generated world fields containing unsupported authority or precision signals as story assumptions before returning them to consumers.

#### Scenario: Generated certification and statistics
- **WHEN** generated world text contains a named certification, a fixed month range, GDP `5.2%`, or venture-capital decline `40%`
- **THEN** every affected field SHALL visibly state that it is a story-setting assumption
- **AND** the qualifier SHALL not be duplicated when processing the result again

#### Scenario: Qualitative world description
- **WHEN** generated world text contains only qualitative contemporary context without authority or precision signals
- **THEN** its prose SHALL remain unchanged

### Requirement: Qualified status survives real storage and display
Qualified world-setting text SHALL survive the real database save-read path and SHALL remain visible to later story consumers and the frontend.

#### Scenario: Saved realistic world
- **WHEN** a qualified realistic world setting is saved and loaded through `GameDatabase`
- **THEN** the loaded character settings SHALL retain the story-assumption qualifier

#### Scenario: Browser opens world settings
- **WHEN** the no-mock browser test opens a game whose real API state contains a qualified world field
- **THEN** the settings panel SHALL visibly show the story-assumption qualifier

### Requirement: Verification is part of the repository gate
Static analysis, import validation, contract tests, real DB tests, and browser tests for this behavior MUST be registered in `test.sh` without mocks or skips.

#### Scenario: Full local verification
- **WHEN** a developer runs the repository test layers with `.env`
- **THEN** each layer SHALL execute the relevant world-fact-safety coverage
