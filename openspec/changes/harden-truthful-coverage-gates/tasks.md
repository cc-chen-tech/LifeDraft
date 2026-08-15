## 1. Failing Governance Contracts

- [x] 1.1 Add no-mock subprocess tests for aggregate coverage success and each single-stage failure.
- [x] 1.2 Add workflow contract tests for real frontend coverage commands, mandatory artifacts, and removal of Codecov.
- [x] 1.3 Add public `./test.sh coverage` subprocess contracts for missing reports, stale cleanup, and stage wiring.

## 2. Truthful Coverage Gates

- [x] 2.1 Make `./test.sh coverage` preserve both stage exit codes, use `npm run test:coverage`, and report only existing outputs.
- [x] 2.2 Enforce `--cov-fail-under=34` in the maintained backend coverage runner while generating `coverage.xml`.
- [x] 2.3 Make `Frontend Tests` and `Coverage Report` upload required repository-owned coverage artifacts.
- [x] 2.4 Reject missing local reports and stop before coverage stages when stale-output cleanup fails.
- [x] 2.5 Verify the exact frontend HTML entry point in `Frontend Tests` and remove obsolete Codecov configuration.

## 3. Verification

- [x] 3.1 Run the targeted coverage governance tests and shell syntax checks.
- [x] 3.2 Run maintained backend coverage, complete frontend coverage, and `./test.sh coverage`.
- [x] 3.3 Run OpenSpec strict validation and confirm the worktree contains only intended changes.
- [x] 3.4 Re-run targeted governance, real backend/frontend coverage, aggregate coverage, and the full local gate after review fixes.
