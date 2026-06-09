# Protagonist Name Drift From Session Display Name - 2026-06-09

## Problem

Production Week 4 QA showed the story body naming the protagonist `心跳测试0737`, while the character settings and relationship text consistently described the canonical player character as `赵谦`.

Evidence:

- `docs/qa-evidence/2026-06-09-heartbeat-1021-production/week4-name-drift-processing.png`
- Production game state for game `105` had `player_state.player_name = 心跳测试0737`.
- The same state had `character_settings.relationships.key_people[].relationship` containing `赵谦（玩家角色）`.

## Root Cause

Story prompt identity resolution preferred `player_state.player_name` before checking the canonical character settings. In production QA accounts, `player_state.player_name` can be a generated test/session display name, while the real role name is only present in structured setting descriptions such as `赵谦（玩家角色）`.

Fallback story generation and scheduled-event prompts also read `player_state.player_name` directly, so failures in the main AI pipeline could reintroduce the same name drift.

## Regression Tests

Added coverage in `tests/test_player_name_in_prompts_contract.py`:

- `test_marked_player_role_name_overrides_generated_session_name`
- `test_round_story_fallback_uses_marked_player_role_name`

These reproduce the production state shape and assert that prompts/fallbacks pin the protagonist as `赵谦`, not `心跳测试0737`.

## Fix

- Added canonical protagonist name resolution in `config/prompts/story_prompts.py`.
- Prefer explicit normal user-provided names, but allow a confidently marked settings name like `赵谦（玩家角色）` to override generated session/test names.
- Reused this resolver in AI round-story fallback and scheduled-event prompt generation.

## Verification

- `pytest tests/test_player_name_in_prompts_contract.py -q` -> 17 passed.

## Status

Fixed locally. Needs push, remote check observation, and ECS deploy if GitHub Actions remain blocked before runner startup.
