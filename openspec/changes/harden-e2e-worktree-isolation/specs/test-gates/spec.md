## ADDED Requirements

### Requirement: E2E gates serialize shared host resources across worktrees
The E2E test gate SHALL require one repository-wide lock for every browser run and MUST NOT allow an environment variable to bypass that lock.

#### Scenario: Another worktree owns the E2E lock
- **WHEN** a developer starts `./test.sh e2e` while a live E2E owner holds the shared lock
- **THEN** the new run MUST exit non-zero before starting backend, frontend, or browser processes and MUST report the owner metadata

#### Scenario: Unsafe parallel override is requested
- **WHEN** a caller sets `TEST_ALLOW_PARALLEL_E2E=1` and starts the E2E gate
- **THEN** the gate MUST exit non-zero and MUST NOT execute the E2E command

### Requirement: E2E lock ownership is recoverable and interruption-safe
The E2E test gate SHALL record lock ownership and SHALL release only the current owner's lock during normal completion or interruption.

#### Scenario: Stale owner is no longer alive
- **WHEN** the lock records an owner PID that is not alive
- **THEN** a new E2E run MUST atomically reclaim the stale lock and execute normally

#### Scenario: E2E owner receives an interruption signal
- **WHEN** the lock-owning test shell receives `SIGINT` or `SIGTERM`
- **THEN** it MUST stop its namespaced runtimes, release its own lock, and exit non-zero

#### Scenario: Lock ownership changed before cleanup
- **WHEN** cleanup observes that the lock owner PID no longer matches the current shell PID
- **THEN** cleanup MUST leave that lock intact

#### Scenario: Owner publication is still in progress
- **WHEN** a contender observes a newly created lock directory before its owner file is published
- **THEN** it MUST preserve the lock and exit non-zero instead of treating the lock as stale

### Requirement: E2E isolation behavior has a non-mocked gate test
The repository SHALL verify lock contention, owner publication, unsafe bypass rejection, stale-lock recovery, and interruption cleanup with real child processes and filesystem state.

#### Scenario: Preflight runs isolation regressions
- **WHEN** `./test.sh preflight` is executed
- **THEN** it MUST run the E2E runtime isolation test file without skip, xfail, process mocks, network mocks, or store mocks
