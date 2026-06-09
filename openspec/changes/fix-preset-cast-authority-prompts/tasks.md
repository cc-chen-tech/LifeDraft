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

## 4. 2026-06-09 Follow-up

- [x] Add a regression test proving scheduled/commitment events inherit protagonist identity, preset cast, and realistic-setting authority constraints.
- [x] Inject the same authority blocks into the scheduled event prompt path so commitment fulfillment cannot bypass the main story prompt guardrails.
- [x] Add a regression test proving scheduled/commitment events retry when generated text replaces the preset cast with invented named substitutes.
- [x] Run scheduled event text through quick validation before returning it to the player.
