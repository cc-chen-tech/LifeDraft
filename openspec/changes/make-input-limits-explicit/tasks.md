## 1. Shared backend request limits

- [ ] 1.1 Add failing tests for every boundary and boundary-plus-one text limit, Unicode measurement, and 256 KiB character-setting JSON measurement.
- [ ] 1.2 Implement the central input-limit registry and apply it only to new-write request models.
- [ ] 1.3 Add failing API tests proving oversized requests return 422 details with field, limit, and actual length and exact-boundary requests pass unchanged.
- [ ] 1.4 Implement structured length-validation responses without changing unrelated validation errors or saved-data reads.

## 2. Eliminate silent truncation

- [ ] 2.1 Replace prompt-sanitizer truncation expectations with failing explicit-exception and no-mutation tests.
- [ ] 2.2 Implement explicit sanitizer length errors and update production callers to surface request validation rather than sliced text.

## 3. Frontend and generated contracts

- [ ] 3.1 Add failing OpenAPI/TypeScript parity tests for all named limits.
- [ ] 3.2 Generate shared frontend constants from the API contract and type affected request payloads against them.
- [ ] 3.3 Add failing component tests for native limits, remaining/over-limit feedback, and blocked oversized submission.
- [ ] 3.4 Implement counters and limit feedback on name, vision/feedback/custom-action, rewrite/chat, replacement-segment, full-story, and voice inputs that are user editable.

## 4. Verification and review

- [ ] 4.1 Run focused schema, API, sanitizer, contract-generation, and frontend component tests.
- [ ] 4.2 Run mypy, imports, contract, DB, strict TypeScript, lint, production build, deterministic Playwright desktop/mobile, and `./test.sh all`.
- [ ] 4.3 Obtain read-only review with no unresolved Critical/Important findings and validate OpenSpec strictly.
- [ ] 4.4 Push a separate stacked branch and open a Draft PR targeting `codex/unify-option-display-budgets`; leave summary/context phases out of scope.
