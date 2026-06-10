## 1. Tests

- [x] Add a contract test for ordinary modern age/career settings that lack explicit modern keywords.
- [x] Add a contract test for missing character settings using the default modern protagonist context.
- [x] Add a contract test for scheduled-event prompts so commitment events cannot bypass modern timeline titles.
- [x] Add a contract test for inline story rewrite prompts so existing classical titles are corrected under modern settings.
- [x] Add the contract test file to `test.sh contract`.

## 2. Fix

- [x] Update Chinese chapter-title classification so non-ancient settings use modern timeline titles.
- [x] Route scheduled-event prompt construction through the same Chinese timeline-title constraint.
- [x] Route rewrite prompt construction through the same Chinese timeline-title constraint.

## 3. Verify

- [x] Run the new contract test before the fix and confirm it fails.
- [x] Run `openspec validate fix-modern-chapter-title-default --strict`.
- [x] Run `./test.sh contract`.
- [x] Run full pre-PR gate before publishing.

## 4. 2026-06-11 Runtime Validation Follow-up

- [x] Add a failing quick-validator regression proving modern stories that start with "第X回" are currently accepted.
- [x] Add a false-positive guard proving explicit ancient stories can still use classical chapter labels.
- [x] Reject classical "第X回" openings during quick validation for modern Chinese character settings.
- [x] Update the story-display-quality spec with runtime validation behavior.
- [x] Add a regression proving plain realistic settings without explicit modern keywords are still validated as modern.
- [x] Narrow ancient era inference so weekday/everyday single characters do not disable modern title validation.
- [x] Add a regression proving timeline title terms such as "周中" are not treated as invented cast members.
