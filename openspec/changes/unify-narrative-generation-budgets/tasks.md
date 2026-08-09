## 1. Budget contracts and compatibility

- [x] 1.1 Add failing tests for all Chinese/English round, opening, and continuation defaults; rewrite 80%-120% derivation; regeneration inheritance; and the 32,000-character absolute limit in `tests/test_narrative_budgets.py`.
- [x] 1.2 Implement enums, immutable budget dataclasses, localized measurement/formatting, the resolver, exhaustion exceptions, and `GenerationCallTracker` in `src/ai/budgets.py`.
- [x] 1.3 Replace `src/ai/generation_budget.py` with a compatibility adapter/re-export and prove old imports and flag-off values remain callable for one release.
- [x] 1.4 Add `ENABLE_UNIFIED_NARRATIVE_BUDGETS=false` to feature-flag settings and environment documentation with parameterized on/off contracts.

## 2. Shared call accounting

- [x] 2.1 Add failing tests that fast/expert/master requests cannot exceed 2/5/7 total provider calls and category allowance is consumed before provider invocation.
- [x] 2.2 Thread one optional request-owned budget/tracker through round and opening generation entry points, Harness validation, consistency repair, and option invocation without changing API response schemas.
- [x] 2.3 Thread the same budget/tracker through continuation, full rewrite, segment rewrite, and regeneration; remove their independent 4096/8192 token ceilings.
- [x] 2.4 Make truncation continuation consume the original prose allowance, enforce the original monotonic deadline, and reject recursive recovery entry while preserving the latest complete narrative.

## 3. Prompt and style migration

- [x] 3.1 Add a failing static contract covering active opening, round, continuation, rewrite, regeneration, Harness repair, and recovery paths for unbudgeted 4096/8192 and conflicting numeric length ranges.
- [x] 3.2 Route all active narrative prompt length instructions through the shared budget formatter and delete 800-1200, 1500-2000, 200-400, and 500-800 product-length literals from critical paths.
- [x] 3.3 Keep legacy `avg_length` readable but exclude it from prompt output; convert every style manifest `avg_length` to relative density/pace language.

## 4. Verification and rollout evidence

- [x] 4.1 Run focused budget, prompt, generation, rewrite, Harness, truncation, opening, and continuation unit/contract tests with unified budgets both enabled and disabled.
- [x] 4.2 Run mypy, import, contract, DB, strict TypeScript, lint, production build, deterministic Playwright desktop/mobile, and final `./test.sh all` in the isolated worktree.
- [x] 4.3 Obtain a read-only code review with no unresolved Critical/Important findings; validate OpenSpec strictly; confirm the worktree diff contains no phase-2 option-display, input-limit, summary, long-context, CI, or DB-cleanup changes.
- [x] 4.4 Push the stacked branch and open a separate Draft PR targeting `codex/preserve-story-on-length-drift`, recording pending remote checks and leaving the rollout flag disabled by default.
