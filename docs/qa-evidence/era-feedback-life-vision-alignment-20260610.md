# Era Feedback Life-Vision Alignment Fix - 2026-06-10

## Reproduction

Two backend regressions were added before implementation:

- Modern vision + feedback: AI returns Tang/Chang'an/imperial-exam era for `2020年代中国互联网公司，成为AI协作工具产品经理`.
- Classical anti-modern vision: AI returns `2026` with internet/AI/company wording for a life vision that asks to avoid modern technology and cyberpunk elements.

Both tests failed on `origin/main` before the fix:

- `assert 713 >= 2020`
- `assert 2026 < 1900`

## Root Cause

`src/game/character_creation.py` had a `feedback` early return in `_align_era_setting_with_life_vision`, so regeneration feedback skipped the existing modern-life-vision correction. The same helper also only corrected ancient-to-modern drift and did not handle explicit anti-modern/classical intent.

## Fix

- Feedback no longer bypasses life-vision era alignment.
- Added anti-modern/classical cues such as `古典`, `传统`, `医者`, `师承`, `乡土`, `避免现代`, and `不要现代`.
- Added historical/classical fallback alignment when the user explicitly rejects modern context.

## Verification

- `python -m pytest tests/test_character_creation_deep.py::TestCharacterCreatorGenerateSetting::test_generate_era_feedback_still_aligns_with_modern_life_vision tests/test_character_creation_deep.py::TestCharacterCreatorGenerateSetting::test_generate_era_prefers_historical_context_when_life_vision_forbids_modern -q`
- `python -m pytest tests/test_character_creation_deep.py -q`
