## 1. Root Cause

- [x] Confirm normal choice continuation already injects required-cast constraints and quick validation.
- [x] Confirm custom-choice JSON result prompt only serialized raw settings and returned the first parsed JSON.
- [x] Reproduce the gap with failing prompt and service-level tests.

## 2. Fix

- [x] Inject preset key-person and world-boundary hard constraints into custom-choice JSON result prompts.
- [x] Validate generated `story_continuation` before returning the JSON result.
- [x] Retry custom-choice JSON generation once when the story violates required-cast constraints.

## 3. Verify

- [x] Run focused custom-choice persona authority tests.
- [x] Run broader preset-cast, quick-validator, and story service tests.
- [x] Run `openspec validate fix-custom-choice-persona-authority --strict`.
- [x] Run project preflight before commit.
