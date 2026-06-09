# 2026-06-09 Late Wealth Sync and Unclosed Dialogue Punctuation

## Summary

Production QA on `story101.live` game `109` found two issues after creating a modern Shanghai indie-game-producer character:

1. The character detail page showed generated initial wealth `¥60,000`, but the `/play` status bar showed `财富: ¥10,000`.
2. The first week story ended with an unclosed Chinese dialogue quote: `“黑眼圈都快掉到下巴了。`

Evidence:

- Browser screenshot: `docs/screenshots-2026-06-09-heartbeat/week1-incomplete-story-wealth-mismatch.png`
- Production route: `https://story101.live/play`
- Observed game id from browser network: `109`

## Root Cause

### Late Wealth Sync

The create flow creates the game before the auto-generated `wealth` setting is available, then later calls `PATCH /api/games/{game_id}/character-settings`. That endpoint merged late `character_settings.wealth` into the saved state but did not synchronize `player_state.wealth`, leaving the playable state at the default `settings.INITIAL_WEALTH` value of `10000`.

### Unclosed Dialogue Quote

Prompt contracts already require correct Chinese punctuation, but `normalize_generated_story` only normalized obvious punctuation artifacts. It did not close an odd-numbered Chinese opening quote when the generated story ended with an unclosed dialogue segment.

## Regression Tests

- `tests/test_character_settings_api_contract.py::TestCharacterSettingsUpdateAPIContract::test_update_character_settings_syncs_late_generated_wealth_before_play`
- `tests/test_gate_gameplay_behavior_no_mock.py::test_generated_story_normalizer_closes_unbalanced_chinese_dialogue_quote`

Both tests were verified red before the fixes and green after the fixes.

## Fix

- `src/api/routers/games.py`
  - Extracts valid late generated `wealth.wealth`.
  - Synchronizes `player_state.wealth` only before the first played round, preventing overwrites of progressed games.
  - Synchronizes the in-memory session game loop as well as the persisted state.
- `src/ai/text_quality.py`
  - Adds a deterministic Chinese quote balancing fallback after normal punctuation cleanup.

## Verification

- `pytest tests/test_character_settings_api_contract.py -q`
- `pytest tests/test_gate_gameplay_behavior_no_mock.py -q -k 'quote or normalizer'`

Status: fixed locally, pending broader gate and deploy.
