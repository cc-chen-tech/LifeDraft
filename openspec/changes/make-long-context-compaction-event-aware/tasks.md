## 1. Whole-event snapshot contract

- [ ] 1.1 Add failing tests for v2 `covered_event_ids`, exact digest coverage, and complete entries.
- [ ] 1.2 Implement schema v2 whole-event packing with `end_event_id` set to the last admitted event.
- [ ] 1.3 Add failing tests proving an unfit event remains raw and no header-only fallback discards history.
- [ ] 1.4 Source snapshot summaries, choices, effects, and event IDs from matching ledger timeline entries with deterministic raw fallbacks.

## 2. Compatibility and prioritized context

- [ ] 2.1 Add failing v1/v2 save, restore, and continuation tests.
- [ ] 2.2 Implement lazy v1 rebuild without database migration or raw-history mutation.
- [ ] 2.3 Add failing tests for current-request, authority, ledger, recent-event, and old-history priority ordering.
- [ ] 2.4 Implement structured dynamic-context admission and explicit `LongContextBudgetError` for required-context overflow.

## 3. Scale and integration

- [ ] 3.1 Add a deterministic 600-event production-budget stress test.
- [ ] 3.2 Wire story and option generation to the prioritized builder while preserving DeepSeek-only activation and stable prefix ordering.
- [ ] 3.3 Add structured telemetry for snapshot schema, covered count, token count, rebuild reason, and degradation without story content.

## 4. Verification and review

- [ ] 4.1 Run focused long-context, ledger, story-generation, save/restore, and strict OpenSpec tests.
- [ ] 4.2 Run mypy, imports, contract, DB, strict TypeScript, lint, production build, deterministic Playwright desktop/mobile, and `./test.sh all`.
- [ ] 4.3 Complete read-only review with no unresolved Critical/Important findings.
- [ ] 4.4 Push a separate stacked branch and open a Draft PR targeting `codex/separate-display-summary-memory`.
