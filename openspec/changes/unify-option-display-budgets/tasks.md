## 1. Display budget and item-level option repair

- [x] 1.1 Add failing localized `DisplayBudget` tests for Chinese/English target and repair thresholds, exactly-three new events, and two-to-four legacy compatibility.
- [x] 1.2 Implement the display-budget resolver and shared measurement helpers without changing stored legacy events.
- [x] 1.3 Add failing generator contracts for preserving valid items, repairing only bad slots, provider failure fallback, uniqueness, and option-call ceilings.
- [x] 1.4 Implement item-level normalization/merge and deterministic contextual completion to exactly three options.

## 2. Frontend display and pending states

- [x] 2.1 Add failing `OptionCards` tests for two-line layout, full accessible text, touch height, disabled peers, and selected loading feedback.
- [x] 2.2 Implement the stable two-line option controls for new and legacy groups.
- [x] 2.3 Add failing play-state tests proving completed story plus missing options renders inline “正在准备选择”, while missing story uses page-level retry.
- [x] 2.4 Implement separate story-pending-options and story-missing retry presentation states.

## 3. Verification and review

- [x] 3.1 Run focused backend option, restore, frontend component, and play-state tests.
- [x] 3.2 Run mypy, imports, contract, DB, strict TypeScript, lint, production build, deterministic Playwright desktop/mobile, and `./test.sh all`.
- [x] 3.3 Obtain read-only review with no unresolved Critical/Important findings and validate OpenSpec strictly.
- [ ] 3.4 Push a separate stacked branch and open a Draft PR targeting `codex/unify-narrative-generation-budgets`; leave later input/summary/context phases out of scope.
