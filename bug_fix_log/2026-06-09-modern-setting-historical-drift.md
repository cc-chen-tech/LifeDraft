# Modern Setting Historical Drift

Date: 2026-06-09
Severity: P1
Status: Fixed locally, pending full-suite verification and deployment

## Production Evidence

- Site: https://story101.live/play
- User flow: new production QA game, Chinese, custom character `林知远`
- Requested setting: contemporary Shanghai, indie game developer, team financing, creative bottlenecks, family relationship pressure, realistic third-person narration.
- Observed screenshot: `/tmp/story101-setting-drift-week1-midweek-20260609-2017.png`
- Observed text snapshot: `/tmp/story101-setting-drift-week1-midweek-20260609-2017.txt`
- Drift evidence: week 1 midweek story moved to `长安西市`, `鲁氏木坊`, `将作监`, `三百文铜钱`, `林郎君`, `慕容娘子`, despite the modern Shanghai character setup.
- UI side effect: the game currency displayed as `文9,995`, reinforcing the same era drift.

## Reproduction

1. Create a new Chinese game on production.
2. In character creation, enter a modern realistic direction:
   `当代上海，独立游戏制作人，围绕团队融资、创作瓶颈、家庭关系与长期主义展开。`
3. Start the game and submit the first choice.
4. Click `进入周中`.
5. Wait for the generated midweek story.
6. The story can drift into ancient Chinese terms and settings instead of preserving the modern setup.

## Root Cause

- `src/ai/harness/era_validator.py` treated modern era contexts as safe and skipped validation.
- Prompt constraints only said modern technology was allowed. They did not explicitly forbid reverse drift into historical dynasties, old city markets, archaic titles, workshops, or pre-modern currency.
- `src/ai/quick_validator.py` did not call the era validator, so the live StoryGenerator fast validation path could accept historical drift even when lower-level validation logic existed.
- `StoryGenerator._extract_validation_context` had been removed while older DB integration tests still depended on that era context contract.

## Fix

- Added reverse-era checks for modern settings in `src/ai/harness/era_validator.py`.
- Added modern-era prompt red lines in `config/prompts/_helpers.py` for dynasty/city/title/currency/workshop drift.
- Wired `src/ai/quick_validator.py` to extract era context from `character_settings` and call `validate_era_consistency`.
- Re-ran quick validation after round-event regeneration; if the retry still drifts, the invalid model output is discarded and local fallback story/options are used instead.
- Restored `StoryGenerator._extract_validation_context` as a compatibility wrapper around the shared quick-validator era extractor.
- Restored minimal optional narrative style initialization hooks so related generation tests can run against current `StoryGenerator`.

## Regression Tests

- `tests/test_era_validator_production_contract.py::test_modern_era_rejects_historical_drift`
- `tests/test_era_validator_production_contract.py::test_quick_validator_rejects_modern_story_historical_drift`
- `tests/test_era_anachronism_contract.py::test_modern_era_prompt_forbids_historical_drift`
- `tests/test_generate_round_event_retry.py::test_round_event_uses_fallback_when_quick_validation_retry_still_drifts`
- Existing DB era integration tests for ancient and modern contexts.

## Verification

- `pytest -q tests/test_era_validator_production_contract.py tests/test_era_anachronism_contract.py tests/test_player_name_in_prompts_contract.py`
  - Result: 41 passed, 1 xfailed
- `pytest -q tests/test_era_validator_integration.py`
  - Result: 3 passed
- `pytest -q tests/test_story_generator_narrative.py tests/test_event_generation_contract.py tests/test_generate_round_event_retry.py`
  - Result: 17 passed
- `pytest -q tests/test_generate_round_event_retry.py tests/test_era_validator_production_contract.py tests/test_era_anachronism_contract.py`
  - Result: 27 passed, 1 xfailed
- `git diff --check`
  - Result: passed

## Follow-Up

- After deployment, repeat production QA from a new modern character and confirm week 1 through week 4 no longer drifts into dynasty/copper-cash vocabulary.
- Consider carrying the selected currency and setting authority into all saved game state surfaces so UI wealth display cannot independently drift.
