## 1. Hermetic Maintained Gates

- [x] 1.1 Add a single maintained-backend runner with normal and coverage modes.
- [x] 1.2 Make the backend and coverage workflows invoke the shared runner.
- [x] 1.3 Make OpenAPI preflight compare temporary generated artifacts without modifying tracked files.

## 2. Browser and Coverage Scope

- [x] 2.1 Remove duplicate core Playwright invocations while retaining targeted AI-heavy regressions.
- [x] 2.2 Exclude frontend test directories from production coverage collection.

## 3. Regression Evidence

- [x] 3.1 Add test-runner contract tests for shared gate membership, hermetic OpenAPI comparison, and non-overlapping browser stages.
- [x] 3.2 Run targeted backend, frontend configuration, OpenSpec, and shell syntax verification.
