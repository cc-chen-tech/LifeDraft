# Narrative Character Drift QA Evidence - 2026-06-10

## Scope

This follow-up closes a remaining character-setting continuity gap in post-choice story continuations.

The ordinary story, round event, scheduled event, and world-model prompts already carried preset cast authority. The uncovered path was the story generated after a player chooses an option: `get_result_generation_prompt` only included a narrow character summary and did not inject the preset key people, realistic-world boundary, or era constraints.

## Reproduction

Red tests added:

- `tests/test_preset_cast_authority_contract.py::test_choice_result_prompt_injects_required_cast_authority_and_world_boundary`
  - Failed because the choice-result prompt did not include `预设关键人物`, `现实主义世界边界`, `禁止赛博朋克`, `夜之城`, or `荒坂集团`.
- `tests/test_story_continuation_drift_contract.py::test_story_continuation_retries_when_choice_result_drifts_from_character_settings`
  - Failed because a post-choice continuation drifting into `夜之城` / `荒坂集团` / `Viktor` was returned after one generation call.
- `tests/test_game_core.py::TestProcessDecision::test_ai_result_generation_passes_character_settings_to_choice_prompt`
  - Failed because the legacy `process_decision` result prompt did not receive `player_state.character_settings`.

## Fix

- Inject full character context, available people, preset key people authority, realistic-world boundary, and era constraints into `get_result_generation_prompt`.
- Add fast local quick-validation and one retry for post-choice continuations in `StoryService.generate_story_continuation`.
- If the retry still drifts, fall back to a local safe continuation instead of returning the drifted story.
- Pass `player_state.character_settings` into the legacy `process_decision` AI result-generation path.

## Verification

Targeted commands:

```bash
pytest tests/test_preset_cast_authority_contract.py -q
pytest tests/test_story_continuation_drift_contract.py -q
pytest tests/test_game_core.py -k "passes_character_settings_to_choice_prompt" -q
```

All targeted tests passed locally after the fix.

Preflight:

```bash
TEST_NAMESPACE=fix-narrative-character-drift-20260610 ./test.sh preflight
```

Result: passed.

- OpenSpec strict gate: 41 passed.
- Backend preflight gate: 121 passed.
- Frontend preflight Jest: 449 passed.
