## 1. Non-Blocking Image Routes

- [x] 1.1 Add failing concurrency and route-contract tests for provider-bound image work
- [x] 1.2 Offload synchronous provider generation and regeneration calls from async image routes
- [x] 1.3 Verify typed provider/content failures preserve their public HTTP mapping

## 2. Proactive Opening Persistence

- [x] 2.1 Add failing frontend tests for completion-time persistence, idempotency, retry, and the two-second start bound
- [x] 2.2 Implement one keyed opening-continuity persistence operation with one retry
- [x] 2.3 Add the duplicate-safe entering state to the opening completion gate

## 3. Verification

- [x] 3.1 Run focused backend and frontend regression tests
- [x] 3.2 Run OpenSpec validation, strict TypeScript, lint, and production build
- [x] 3.3 Run the repository integration gate and review the scoped diff
