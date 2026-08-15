## ADDED Requirements

### Requirement: Real database test runs are isolated from developer data
Every repository-owned test entry point that initializes the application database SHALL create a unique SQLite database below a controlled per-run directory and SHALL explicitly provide its URL before database modules are imported.

#### Scenario: Public DB layer runs
- **WHEN** a developer executes `./test.sh db`
- **THEN** database initialization and pytest MUST receive the same `DATABASE_URL` for a unique database below `$TEST_RUN_DIR/data/`

#### Scenario: Maintained backend suite runs
- **WHEN** the maintained backend runner executes in test or coverage mode
- **THEN** it MUST create, initialize, use, and clean an independent SQLite database for that invocation

#### Scenario: Make or pre-commit starts pytest
- **WHEN** a repository Make target or pre-commit option executes pytest
- **THEN** it MUST use the shared isolation boundary with the same Python interpreter for initialization and tests

#### Scenario: Ambient configuration targets another database
- **WHEN** the process environment or `.env` supplies `DATABASE_URL`, or the repository contains `data/game.db`
- **THEN** real-database test entry points MUST override those targets and MUST NOT modify them

#### Scenario: Runs repeat
- **WHEN** a real-database test entry point is executed more than once
- **THEN** each invocation MUST receive an empty database at a different path and MUST NOT share persisted state

#### Scenario: An isolated test fails or is terminated
- **WHEN** the test command exits non-zero or the isolation wrapper receives INT, TERM, or HUP
- **THEN** the wrapper MUST preserve the expected status, terminate its child process group, and clean the database and sidecar files

### Requirement: CI delegates database ownership to test runners
Backend CI workflows SHALL rely on the maintained backend runner to create and initialize its isolated database.

#### Scenario: Backend workflow starts maintained tests
- **WHEN** a backend test or coverage workflow runs
- **THEN** it MUST NOT initialize the application database before invoking the maintained backend runner
