## 1. Reproduce

- [x] Confirm frontend game creation can omit the just-accepted world setting.
- [x] Confirm backend auto-matched style is not present in initial session state.

## 2. Tests

- [x] Add frontend regression test for accepted world in `/api/games` payload.
- [x] Add backend regression test for auto-matched style in `initial_state` and loaded `GameLoop`.

## 3. Fix

- [x] Use accepted settings snapshot during initial game creation.
- [x] Persist auto-matched style into initial state.

## 4. Verify

- [x] Run `pytest tests/test_style_matcher.py -q`.
- [x] Run `cd frontend && npx jest --runTestsByPath src/__tests__/hooks/useCharacterCreation.test.ts --runInBand`.
- [x] Run full pre-PR test gate before publishing.
