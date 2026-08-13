## 1. Display summary budgets

- [x] 1.1 Add failing Chinese/English tests for week, month, year, and life target bands and measurement units.
- [x] 1.2 Implement shared display-summary budget resolution and prompt formatting.
- [x] 1.3 Add failing tests proving oversized summaries end on complete sentence boundaries and are never raw-sliced.
- [x] 1.4 Implement sentence-aware display compaction for all shared summary return paths.

## 2. Shared generation and compatibility

- [x] 2.1 Add failing tests proving weekly, monthly, and yearly compatibility generators delegate prose generation to `SummaryGenerator` and preserve their public result shapes.
- [x] 2.2 Implement shared week/month/year/life display-summary entry points and convert legacy classes into compatibility wrappers.
- [x] 2.3 Remove conflicting numeric summary targets from active wrapper prompts while preserving fallback behavior.

## 3. Structured memory independence

- [x] 3.1 Add failing choice-finalization tests proving a display-summary failure does not roll back ledger commits.
- [x] 3.2 Add failing extraction-failure tests proving deterministic choice, effects, source event ID, and existing authority remain recorded.
- [x] 3.3 Route model-memory reads through `ContinuityLedger` under `ENABLE_STRUCTURED_STORY_MEMORY`, with legacy summary reads retained when disabled.

## 4. Verification and review

- [x] 4.1 Run focused summary, ledger, finalizer, and compatibility tests plus strict OpenSpec validation.
- [ ] 4.2 Run mypy, imports, contract, DB, strict TypeScript, lint, production build, deterministic Playwright desktop/mobile, and `./test.sh all`.
- [ ] 4.3 Complete read-only review with no unresolved Critical/Important findings.
- [ ] 4.4 Push a separate stacked branch and open a Draft PR targeting `codex/make-input-limits-explicit`.
