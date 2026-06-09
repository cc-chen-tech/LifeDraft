## 1. Tests

- [x] Add no-mock import validation for the preset relationship authority module and wire it into `test.sh imports`.
- [x] Add contract tests for canonical preset cast extraction, story prompt injection, and WorldModel constraint injection.
- [x] Run the new tests before implementation and confirm they fail for the missing behavior.

## 2. Implementation

- [x] Implement canonical preset cast extraction and constraint text generation.
- [x] Inject required cast constraints into story-only and round-event prompts.
- [x] Add required cast constraints to WorldModel built from player state.

## 3. Verification

- [x] Run targeted import and contract tests.
- [x] Run `openspec validate fix-preset-cast-authority-prompts --strict`.
- [x] Run `./test.sh all`.
