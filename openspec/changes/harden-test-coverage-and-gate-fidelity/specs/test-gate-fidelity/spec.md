## ADDED Requirements

### Requirement: Coverage modes are explicit
The system SHALL distinguish maintained-gate coverage from full-suite coverage in local commands, CI job names, and generated reports.

#### Scenario: Maintained backend coverage is reported
- **WHEN** the maintained backend coverage command runs
- **THEN** the output and CI job name identify it as maintained-gate coverage rather than full backend coverage

#### Scenario: Full backend coverage is reported
- **WHEN** the full backend coverage command runs
- **THEN** the output identifies it as full-suite coverage and does not imply merge readiness unless the full suite passes

### Requirement: Gate wiring cannot silently drift
The system SHALL provide tests or contracts that verify new maintained gate suites are wired into `test.sh` and the corresponding CI coverage selection.

#### Scenario: New contract test is added to test.sh
- **WHEN** a new maintained backend contract test is listed in `test.sh contract`
- **THEN** a coverage wiring check fails if the maintained backend coverage workflow omits that test without an explicit exclusion reason

#### Scenario: New DB test is added to test.sh
- **WHEN** a new maintained real-DB test is listed in `test.sh db`
- **THEN** a coverage wiring check fails if the maintained backend coverage workflow omits that test without an explicit exclusion reason

### Requirement: Stale backend tests are classified before broad repair
The system SHALL classify failing legacy backend tests before using them as implementation requirements.

#### Scenario: Legacy test asserts removed internals
- **WHEN** a failing legacy test asserts an implementation detail that no longer exists
- **THEN** the test is marked for contract update or explicit exclusion rather than forcing production code to restore the old internal detail

#### Scenario: Legacy test asserts current user-visible behavior
- **WHEN** a failing legacy test describes current user-visible behavior or a still-valid API contract
- **THEN** production code or test setup is fixed so the behavior passes

### Requirement: High-risk state paths receive focused coverage
The system SHALL prioritize focused unit or integration coverage for state-machine paths that affect story reading, scene images, music playback, SSE recovery, and save/load recovery.

#### Scenario: Story voice store handles request success
- **WHEN** a voice reading request returns a ready audio asset
- **THEN** focused frontend tests verify reading state, job id, audio URL, source, context label, and text hash behavior

#### Scenario: Story voice store handles request failure
- **WHEN** a voice reading request fails
- **THEN** focused frontend tests verify failure state, retry state, and music ducking restoration behavior

#### Scenario: Scene image and music state coverage is raised
- **WHEN** scene image or music queue state changes are modified
- **THEN** focused frontend tests cover cache refresh, queue preservation, failure recovery, and user intent preservation

### Requirement: Coverage thresholds are staged
The system SHALL enforce coverage thresholds only for suites whose scope and reliability are explicit.

#### Scenario: Maintained backend threshold is introduced
- **WHEN** maintained backend coverage runs in CI
- **THEN** it enforces a threshold appropriate to the maintained subset and documents that the number is not full-suite coverage

#### Scenario: First threshold ratchet is reached
- **WHEN** stable high-risk backend contract and DB groups are promoted into maintained coverage
- **THEN** maintained backend coverage SHALL enforce at least 30% line coverage locally and in CI

#### Scenario: Full backend threshold is deferred
- **WHEN** the full backend suite contains known stale failures
- **THEN** full backend coverage may be generated for visibility but SHALL NOT be treated as a blocking full-suite threshold

### Requirement: Unit test logs remain actionable
The system SHALL reduce routine test log noise while preserving intentional assertions for error and warning paths.

#### Scenario: Expected console errors are tested
- **WHEN** a frontend unit test exercises an expected error path
- **THEN** the test either asserts the console output intentionally or suppresses it through a shared helper

#### Scenario: Unexpected console errors occur
- **WHEN** a frontend unit test emits an unexpected console error
- **THEN** the test output remains visible enough to identify the failure source
