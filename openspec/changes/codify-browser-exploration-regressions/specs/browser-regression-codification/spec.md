## ADDED Requirements

### Requirement: Browser findings are codified in maintained tests
Browser-agent findings that affect creation, gameplay progression, story continuity, history review, scene images, collection refresh, ChatBar interaction, rewrite/regenerate, or music fallback SHALL have deterministic regression tests in maintained gates.

#### Scenario: Finding becomes a maintained regression
- **WHEN** a browser exploration finding maps to stable frontend state or component behavior
- **THEN** a Jest preflight test MUST assert the invariant without requiring external AI, image, or music providers

#### Scenario: Browser-only finding stays in Playwright
- **WHEN** a finding depends on browser pointer hit-testing, layout, or route-level user interaction
- **THEN** a no-mock Playwright regression MUST assert the invariant with stable roles or test IDs

### Requirement: Deep exploration remains discoverable
The deep browser exploration sweep SHALL remain wired into the e2e test command so broad gameplay validation can still be run intentionally.

#### Scenario: E2E command includes deep exploration
- **WHEN** maintainers run the project e2e test command
- **THEN** the Story101 deep exploration spec MUST be included or explicitly documented as a separate command in `test.sh`

### Requirement: Maintained gates include browser regression tests
The maintained preflight gate SHALL include the frontend tests that codify browser-agent regressions and SHALL fail if those files drift out of gate wiring.

#### Scenario: Preflight covers codified regressions
- **WHEN** `./test.sh preflight` runs
- **THEN** it MUST validate the browser regression OpenSpec change and execute the maintained frontend regression tests

#### Scenario: Gate fidelity catches omissions
- **WHEN** a maintained regression file is added for browser findings
- **THEN** a gate fidelity test MUST fail unless that file is represented in the appropriate `test.sh` gate
