## 1. Isolation Contracts

- [x] 1.1 Add static governance tests for public, maintained-runner, and workflow database ownership
- [x] 1.2 Add a real subprocess regression for unique database paths, empty repeated runs, cleanup, and ambient database protection
- [x] 1.3 Run the new tests and record their expected pre-implementation failures
- [x] 1.4 Add real subprocess coverage for non-zero exits and INT/TERM cleanup

## 2. Database Lifecycle

- [x] 2.1 Add a shared shell helper that creates, initializes, exposes, and cleans a unique SQLite test database
- [x] 2.2 Route `./test.sh db` through the helper below `$TEST_RUN_DIR/data/`
- [x] 2.3 Route maintained backend test and coverage modes through the helper
- [x] 2.4 Route Make and opt-in pre-commit pytest commands through the helper with their selected Python interpreter
- [x] 2.5 Forward termination signals to the isolated child process group and preserve exit status

## 3. Workflow Ownership

- [x] 3.1 Remove standalone database initialization from backend and coverage workflows
- [x] 3.2 Keep existing E2E database setup unchanged

## 4. Verification

- [x] 4.1 Run database-isolation governance tests and shell syntax checks
- [x] 4.2 Run `./test.sh db` and maintained backend test and coverage modes locally
- [x] 4.3 Verify repeated runs and the repository `data/game.db` fingerprint remain isolated
- [x] 4.4 Run OpenSpec strict validation and the complete local `./test.sh all` gate
