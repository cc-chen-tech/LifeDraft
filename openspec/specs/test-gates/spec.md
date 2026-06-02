# test-gates Specification

## Purpose
TBD - created by archiving change fix-story-continuity-history-media. Update Purpose after archive.
## Requirements
### Requirement: Changes are test-first
The system development workflow SHALL add failing tests for each bug fix or new feature before production code is changed.

#### Scenario: Bug fix begins
- **WHEN** a bug fix task starts
- **THEN** the relevant static, import, contract, DB, frontend, or E2E test coverage MUST be added before production code changes for that task

#### Scenario: New feature begins
- **WHEN** a new feature task starts
- **THEN** acceptance tests for the new behavior MUST be added before production code changes for that feature

### Requirement: Test gates are available from test.sh
The repository SHALL expose all required verification layers through `test.sh`.

#### Scenario: Full verification
- **WHEN** `./test.sh all` is executed
- **THEN** it MUST run static analysis, import validation, contract tests, real DB integration tests, and E2E browser tests

#### Scenario: Individual verification layer
- **WHEN** a developer runs `./test.sh mypy`, `./test.sh imports`, `./test.sh contract`, `./test.sh db`, or `./test.sh e2e`
- **THEN** only the requested verification layer MUST run and return a non-zero exit code on failure

### Requirement: Static analysis uses strict mypy behavior
The static analysis layer SHALL catch type mismatches and missing attributes in changed backend code.

#### Scenario: Mypy layer runs
- **WHEN** `./test.sh mypy` is executed
- **THEN** mypy MUST run in strict mode for the relevant source tree or changed strict modules

### Requirement: Import validation covers lazy imports
The import validation layer SHALL verify delayed import paths used by gameplay, image, session, and collection code.

#### Scenario: Lazy import path broken
- **WHEN** a delayed import path references a missing module, class, or function
- **THEN** the import validation tests MUST fail

### Requirement: Contract tests verify producer and consumer fields
The contract layer SHALL verify that backend API response fields match frontend consumer field names for gameplay, history images, and collection data.

#### Scenario: Backend response field renamed
- **WHEN** a backend response omits or renames a field consumed by the frontend
- **THEN** contract tests MUST fail before E2E tests run

### Requirement: Real DB integration verifies save-read chains
The DB integration layer SHALL use a real database session and verify complete save-to-read behavior for affected persisted state.

#### Scenario: Round history persistence
- **WHEN** gameplay state with round history and current event data is saved then loaded
- **THEN** the loaded state MUST preserve the fields required by history review and choice recovery

#### Scenario: Scene image persistence
- **WHEN** a scene image record is saved then queried by game, week, round, and stage
- **THEN** the loaded record MUST match the saved key fields and image metadata

### Requirement: E2E browser tests cover visible interactions
The E2E layer SHALL exercise browser-visible progress, history, and panel interactions without frontend or network mocks.

#### Scenario: History panel interaction
- **WHEN** a browser E2E test opens the play regression page and selects a historical round
- **THEN** it MUST observe historical text and matching image state without network mocking

#### Scenario: Collection panel interaction
- **WHEN** a browser E2E test opens collection-related UI
- **THEN** it MUST observe stable loading/progress or panel interaction behavior without network mocking

### Requirement: Gate tests do not skip or mock
Tests added for this change SHALL NOT use skip, xfail, mocked APIs, mocked stores, or mocked network responses.

#### Scenario: Test file reviewed
- **WHEN** a gate test file for this change is inspected
- **THEN** it MUST NOT contain skip/xfail directives or mocking constructs

### Requirement: Regression tests cover live-discovered gameplay failures
The test gates SHALL include regressions for each live-discovered blocking gameplay failure.

#### Scenario: Opening story SSE parser regression
- **WHEN** frontend tests exercise opening-story SSE parsing
- **THEN** they MUST fail if `event: story` payloads are ignored

#### Scenario: Recovery no-empty-story regression
- **WHEN** frontend store tests recover an event with options
- **THEN** they MUST fail if `storyText` remains empty

#### Scenario: Scene image state-source regression
- **WHEN** backend tests request a missing scene image with persisted current event text
- **THEN** they MUST fail if the endpoint reads `Game.player_state` or returns `404` instead of triggering generation

