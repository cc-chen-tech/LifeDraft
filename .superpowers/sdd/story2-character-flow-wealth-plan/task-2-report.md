# Task 2 Report — Remove the Wealth System

## Scope and identity

- Worktree: `/Users/luicy/story2/.worktrees/remove-wealth-system`
- Branch: `codex/remove-wealth-system`
- Baseline: `bca973c267e641ce5cde93ae9ec3cf51c6ea46aa`
- Implementation commit: `a7d3754a` (`feat: remove wealth system`)
- Requirements source: `task-2-brief.md`; exact thresholds and compatibility rules were implemented as written.

## Dependency inventory

The initial `git grep` inventory contained 1,280 textual matches and 139 runtime/test files. Natural-language uses in narrative/style/history were separated from technical wealth state. No fragile repository-wide word-ban test was added.

### Runtime dependency surface found and handled

- Prompts/config: `config/prompts/_helpers.py`, `character_prompts.py`, `story_prompts.py`, `summary_prompts.py`, `config/settings.py`.
- AI models/generation/validation: `src/ai/models.py`, `cache.py`, `consistency_validator.py`, `generator.py`, `option_generator.py`, `quick_validator.py`, `story_generator.py`, `summary_generator.py`, `system_prompts.py`, `text_quality.py`, `harness/validators.py`.
- State and game initialization: `src/game/state/player_data.py`, `player_logic.py`, `player_state.py`, `game_initializer.py`, `constants.py`, `game_loop.py`, `fallback_events.py`.
- Choice/round/world flow: `src/game/decisions.py`, `round/choice_processor.py`, `round/finalizer.py`, `story_service.py`, `assistant_grounding.py`, `world_model.py`.
- Summaries/outcomes: `weekly_summary.py`, `monthly_summary.py`, `yearly_summary.py`, `endings.py`, `achievements.py`, `life_review.py`, `src/services/life_summary_grounding.py`.
- API: `src/api/schemas.py`, `routers/character.py`, `routers/games.py`, `routers/presets.py`, plus regenerated OpenAPI schema/types.
- Frontend: create-flow hook/store/completion, public types, session state comparison, setting/impact/life-review display, e2e-regression fixtures, and generated API types.
- Dedicated wealth implementation/tests: `src/game/wealth_ledger.py`, two backend ledger suites, currency contract, and the wealth-ledger Playwright suite.

### Test/fixture dependency surface found

The inventory covered backend state, game, API, creation, choice/finalizer, summary, ending/achievement/life-review, prompt, persistence, DB and integration fixtures; and frontend create/store/type/display/ending/session suites plus E2E fixtures. Tests that merely carry legacy wealth keys remain useful compatibility fixtures when they do not assert the retired behavior. Historical docs and natural narrative wording were intentionally not rewritten.

## TDD evidence

### RED

Backend command:

```text
./venv/bin/python -m pytest -q tests/test_wealth_removal_contract.py
```

Initial result: **9 failed / 9 collected**, demonstrating missing contracts for recursive legacy-key cleanup, the three-resource effect allowlist, Pydantic rejection of `setting_type=wealth`, clean new-game/preset state, qualitative-only summaries, exact ending/achievement rules, and three-resource life-review curves.

Frontend command:

```text
npx jest src/__tests__/wealthRemoval.contract.test.tsx --runInBand --no-cache
```

Initial result: **2 failed / 3 collected**: the create flow still advanced through wealth and legacy wealth settings were still rendered.

### GREEN

- New backend contract: **9/9 passed**.
- New frontend contract: **3/3 passed**.
- Final focused backend regression: **240/240 passed** across removal, endings, achievements/life review, character/settings APIs, games, state serialization, weekly/monthly/yearly summaries, choice processing, and finalization.
- Final focused frontend regression: **211/211 passed** across removal, create flow, game store, setting display, choice impact, and life review.
- Frontend strict typecheck: `tsc --noEmit --strict` passed.
- Python 3.11 imports: `./test.sh imports`, **52/52 passed**.
- Python 3.11 strict type gate: `./test.sh mypy`, **17 source files checked with no issues; 5/5 static gates passed**.
- Python compilation/import smoke: `compileall` plus imports of FastAPI app, `PlayerState`, and `EventGenerator` passed.
- Generated OpenAPI schema and TypeScript declarations were refreshed and strict-checked.
- `git diff --check` passed. New Python files pass Black formatting.

## Implemented behavior

- `EventOption`, legacy decision processing, choice processing, custom effects, and weekly bonuses now retain only integer `energy`, `mood`, and `knowledge` effects. Wealth and every other unexpected effect are silently dropped.
- `wealth`, `wealth_ledger`, and `_active_wealth_transaction_id` are recursively stripped by exact key when old state/settings/presets are read. Preset writes are also sanitized. No bulk migration is performed; subsequent ordinary saves contain the cleaned model.
- `GenerateSettingRequest.setting_type` is a `Literal` excluding wealth, so requests are rejected with 422 during Pydantic validation before the creator is called.
- Numeric wealth state, initialization, bounds, ledgers, transactions, cache keys, prompt variables, story/summary balance constraints, precise continuity checks, grounding evidence, and frontend public state/display were removed.
- Qualitative economic narrative remains allowed. The life-summary grounding filter no longer mistakes ordinary uses of “wealth/财富” for a retired game metric.
- Ending priority is exactly: struggling when three-resource average `< 40`; scholar when `knowledge > 80` and average `> 60`; social when at least three relationships have average affinity `> 70`; otherwise balanced. Wealthy ending and wealth final stats are gone.
- Achievements remove `steady_climber` and `rags_to_riches`; equilibrium/neutral use three resources; tragic hero compares the summed three-resource effects across history halves and requires mood `< 40`; legendary tale requires 50 rounds without wealth.
- Resource curves, summaries, generated attributes, public TypeScript types, and OpenAPI types expose only the three active resources.

## Compatibility strategy

- Exact retired keys only are removed recursively; similarly named prose fields are not globally stripped.
- Cleanup happens at state/preset ingress and normal save serialization rather than via a one-time database migration.
- Legacy wealth setting UI input is hidden without displaying an empty card; legacy wealth impact entries are suppressed.
- Ordinary narrative about work, money, business, hardship, or wealth remains legal when it is qualitative and not backed by technical balance/state continuity.

## Deleted files

- `src/game/wealth_ledger.py`
- `tests/test_wealth_ledger.py`
- `tests/test_wealth_ledger_integration.py`
- `tests/test_currency_contract.py` (dedicated technical currency/wealth contract)
- `frontend/e2e/wealth-ledger.spec.ts`

## Added files

- `src/game/effects.py`
- `src/utils/legacy_data.py`
- `tests/test_wealth_removal_contract.py`
- `frontend/src/__tests__/wealthRemoval.contract.test.tsx`

## Modified file groups

- Four prompt/config modules and settings.
- Eleven AI model/generation/validation modules.
- Twenty state/game/round/world/summary/outcome modules.
- Four API modules plus two generated API artifacts.
- Eleven frontend runtime modules and four frontend unit suites.
- Twenty-seven backend contract/fixture suites plus `test.sh` gate manifests.

The exact committed file list is available with:

```text
git diff --name-status bca973c2..a7d3754a
```

## Remaining concerns

- Full browser E2E was intentionally not run in this worktree; the parent integration agent will run it serially.
- A broad non-E2E backend snapshot before all task-related test updates was 3,587 passed, 46 failed, 10 errors. All wealth-caused failures from that snapshot were addressed and the 240-test focused set is green.
- Independently reproduced failures outside this task remain in `tests/test_generate_round_event_retry.py` (four tests: expert attempts, master attempts, validation fallback, required-cast fallback) and `tests/test_events.py::TestEventGenerator::test_generate_event_mock`; they concern story retry/fallback or forbidden “Option” wording and do not traverse wealth-removal code.
- The broad run also observed unrelated image-provider configuration assertions, SSE shutdown/order state, and style-endpoint authentication failures. They were not modified to avoid expanding scope.
- An initial broad frontend baseline had a pre-existing `SavesPage` timing failure and then hit disk pressure; focused frontend tests and strict typecheck are green after disk cleanup.

## Commits

- `a7d3754a` — `feat: remove wealth system`
- Report commit — branch HEAD after this report is committed.
