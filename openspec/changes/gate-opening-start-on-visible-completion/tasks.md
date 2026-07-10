## 1. Test-First Completion Contracts

- [x] 1.1 Add immutable no-mock component tests for exact visible-text completion callbacks
- [x] 1.2 Add an immutable opening-page test proving the start control stays unavailable until visible completion
- [x] 1.3 Add and register a no-mock Playwright test in `test.sh`, then record RED failures

## 2. Visible Completion Gate

- [x] 2.1 Implement deduplicated `StreamingText` visible-completion reporting
- [x] 2.2 Gate opening navigation on matching SSE and visible completion state
- [x] 2.3 Reset visible completion for retries, text replacement, and stale callbacks

## 3. Verification and Delivery

- [x] 3.1 Run focused Jest and Playwright tests with the repository `.env`
- [x] 3.2 Run OpenSpec strict validation and all five `test.sh` layers without skips
- [x] 3.3 Commit, push, open a ready PR, and resolve CI failures
