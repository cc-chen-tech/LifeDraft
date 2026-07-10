## 1. Regression Tests (RED)

- [x] 1.1 Add a non-mocked subprocess test proving a live owner blocks a second worktree and reports owner metadata.
- [x] 1.2 Add a non-mocked subprocess test proving `TEST_ALLOW_PARALLEL_E2E=1` is rejected before its command runs.
- [x] 1.3 Add non-mocked subprocess tests for stale-lock recovery, signal cleanup, and mismatched-owner protection.
- [x] 1.4 Register the immutable isolation regression file in `test.sh preflight` and verify the new tests fail for the expected missing behavior.

## 2. Lock Implementation (GREEN)

- [x] 2.1 Make `test.sh` sourceable without executing its command dispatcher.
- [x] 2.2 Implement mandatory owner-aware E2E lock acquisition and unsafe bypass rejection.
- [x] 2.3 Implement atomic stale-lock recovery and owner-matching release.
- [x] 2.4 Implement normal, failure, `SIGINT`, and `SIGTERM` cleanup for namespaced runtimes and lock ownership.
- [x] 2.5 Run the immutable isolation regression file and confirm it passes.
- [x] 2.6 Preserve browser fallback mode, text, and length in the initial loading state without starting speech.
- [x] 2.7 Run the unchanged guest voice E2E repeatedly and confirm the `none` loading state no longer appears.
- [x] 2.8 Start an explicitly selected browser provider immediately while preserving its real backend recording request.
- [x] 2.9 Run the unchanged complete voice-reading spec repeatedly with zero failures and zero flaky retries.
- [x] 2.10 Add an immutable regression proving a fresh ownerless lock cannot be reclaimed during owner publication, then implement the age guard.

## 3. Verification

- [x] 3.1 Run OpenSpec strict validation and targeted preflight tests.
- [x] 3.2 Run mypy strict, import validation, contract, and real DB integration layers through `test.sh` with the repository `.env` exported to the process.
- [x] 3.3 Run repeated clean voice-reading E2E and the full browser gate through `test.sh` with isolated runtime state.
- [x] 3.4 Run `./test.sh all`, inspect the final diff, and confirm no tests are skipped or mocked.
- [x] 3.5 Commit the verified change, push the branch, open a ready PR, and inspect all PR checks.
