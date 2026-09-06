## 1. Regression Tests

- [x] 1.1 Add quick-validator regressions for seven-person 4/7 and 5/7 stories with no coverage finding.
- [x] 1.2 Add regressions for explicit required-person omission and invented-role takeover remaining hard failures.
- [x] 1.3 Add object/place/organization noise regressions and verify low coverage does not trigger round-event retry.
- [x] 1.4 Update preset-cast prompt contract assertions to remove the global 80% rule while retaining no-substitution authority.

## 2. Implementation

- [x] 2.1 Remove aggregate coverage findings from quick validation without changing the public validator API.
- [x] 2.2 Preserve explicit required-cast and high-confidence takeover hard gates.
- [x] 2.3 Remove the global 80% instruction from shared relationship-authority prompts.
- [x] 2.4 Keep historical `CAST_COVERAGE_LOW` message parsing compatible.

## 3. Verification

- [x] 3.1 Run targeted cast-authority and retry tests with the shared Python environment.
- [x] 3.2 Run OpenSpec strict validation for this change.
- [x] 3.3 Run `./test.sh preflight`, `./test.sh quick`, `./test.sh contract`, `./test.sh db`, and `./test.sh e2e`.
- [x] 3.4 Review the final diff, commit, push the branch, and open the PR without merging or deploying.
