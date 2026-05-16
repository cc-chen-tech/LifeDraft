## 1. Tests First

- [x] 1.1 Add no-mock backend route-table contract tests for browser API-contract endpoints.
- [x] 1.2 Add no-mock deprecated endpoint absence tests.
- [x] 1.3 Add gate wiring tests proving the shift-left checks run before E2E.

## 2. Gate Wiring

- [x] 2.1 Wire the shift-left route contract into `test.sh contract`.
- [x] 2.2 Wire the OpenSpec validation into `test.sh preflight`.

## 3. Verification

- [x] 3.1 Run `openspec validate shift-left-e2e-contract-gates --strict`.
- [x] 3.2 Run the new route contract test.
- [x] 3.3 Run `./test.sh preflight` and `./test.sh contract`.
