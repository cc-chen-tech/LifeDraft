## 1. Contract Tests

- [x] 1.1 Add hard REST field alignment tests for backend schemas, OpenAPI schema, generated bridge types, hand-written frontend types, and API wrapper annotations.
- [x] 1.2 Add mock/fixture source scans for critical game state and round scene image payload fields.
- [x] 1.3 Add explicit SSE payload field contract coverage for scene image and gameplay parser-facing events.

## 2. Gate Wiring

- [x] 2.1 Wire the field-contract test file and OpenSpec validation into `test.sh preflight` and `test.sh contract`.
- [x] 2.2 Wire the field-contract test file into maintained backend CI/coverage pytest lists.

## 3. Verification

- [x] 3.1 Run the new focused field-contract test file.
- [x] 3.2 Run `openspec validate harden-frontend-backend-field-contracts --strict`.
- [x] 3.3 Run maintained/preflight gates affected by this change.
