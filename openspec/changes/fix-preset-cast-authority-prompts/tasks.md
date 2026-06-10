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

## 5. 2026-06-10 Follow-up

- [x] Add a regression test proving choice-result prompts inherit preset cast authority and realistic-setting boundaries.
- [x] Inject preset cast authority, available people, era constraints, and modern-world boundaries into post-choice continuation prompts.
- [x] Add a regression test proving post-choice continuations retry when generated text drifts into external IP or invented cast.
- [x] Run choice-result continuations through quick validation before returning or saving them.
- [x] Pass `PlayerState.character_settings` into the legacy `process_decision` result-generation path.

## 6. 2026-06-10 Required Cast Presence Follow-up

- [x] Add regression assertions proving preset-cast prompts require at least one canonical preset key person per round.
- [x] Extend the shared relationship authority prompt block so story-only, round-event, choice-result, scheduled-event, and WorldModel paths inherit the same presence requirement.
- [x] Run targeted preset-cast contract tests.

## 7. 2026-06-10 Story Character Sync Follow-up

- [x] Add a regression test proving story-character sync does not promote a named substitute for a preset role.
- [x] Skip automatic key_people promotion when a new name appears in the local context of an existing preset role/relationship token.
- [x] Run the targeted world model updater character-sync tests.

## 8. 2026-06-10 Legacy Relationships Payload Follow-up

- [x] Add regression tests proving prompt injection and quick validation still work when `character_settings.relationships` is a legacy list payload.
- [x] Normalize legacy relationship list payloads in the shared available-people and required-cast extractors.
- [x] Run targeted preset-cast and game creation contract tests.

## 9. 2026-06-10 Regenerate Drift Follow-up

- [x] Add a regression test proving full story regeneration retries when the first regenerated story drops preset key people and drifts into invented cast/IP-world content.
- [x] Run regenerated story text through quick validation before returning it when no WorldModel is available.
- [x] Run targeted story continuation and preset-cast contract tests.

## 10. 2026-06-10 Segment Rewrite Drift Follow-up

- [x] Add a regression test proving segment-level rewrite retries when the first rewritten story drops preset key people and drifts into invented cast/IP-world content.
- [x] Run rewritten story text through quick validation before returning it when no WorldModel is available.
- [x] Run targeted story continuation and preset-cast contract tests.

## 11. 2026-06-11 Main Event Prompt Follow-up

- [x] Add a regression test proving the main event prompt injects the required preset-cast authority block, not only the loose available-people list.
- [x] Inject required cast constraints into the Chinese and English main event prompt paths.
- [x] Run targeted prompt contract and adjacent narrative drift tests.
