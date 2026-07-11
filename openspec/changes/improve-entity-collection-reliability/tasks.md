## 1. Immutable Test-First Contracts

- [x] 1.1 Add no-mock recognition tests for prose-only people, false positives, and sentence-complete summaries, then record expected RED failures
- [x] 1.2 Add no-mock import, producer-consumer contract, and real DB add-read tests, then record expected RED failures
- [x] 1.3 Add a no-interception browser test for add completion and register all new tests in `test.sh`

## 2. Recognition and Add Reliability

- [x] 2.1 Admit deterministic explicit people alongside metadata while preserving exclusions
- [x] 2.2 Replace fixed-window fallback contexts with normalized sentence-aware excerpts
- [x] 2.3 End blocking add state after durable POST and run details hydration as a non-blocking refresh

## 3. Verification and Delivery

- [x] 3.1 Run focused RED/GREEN tests with the repository `.env`
- [x] 3.2 Run strict OpenSpec validation and all five `test.sh` layers without skips
- [x] 3.3 Commit, push, open a ready PR, and resolve CI failures
